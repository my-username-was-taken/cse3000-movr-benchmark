#include "workload/movr.h"

#include <glog/logging.h>

#include <random>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#include "common/proto_utils.h"
#include "execution/movr/constants.h"
#include "execution/movr/transaction.h"
#include "execution/movr/data_generator.h"

using std::bernoulli_distribution;
using std::iota;
using std::sample;
using std::string;
using std::unordered_set;

using slog::movr::DataGenerator;
using slog::movr::kDefaultUsers;
using slog::movr::kDefaultVehicles;
using slog::movr::kDefaultRides;
using slog::movr::kDefaultCities;

namespace slog {
namespace {

// Existing parameters (copied from TPCC)
constexpr char PARTITION[] = "partition"; // Use specific partition, -1 for random
constexpr char HOMES[] = "homes";         // Max number of regions accessed in a multi-home txn
constexpr char MH_ZIPF[] = "mh_zipf";     // Zipf coefficient for selecting remote regions
constexpr char TXN_MIX[] = "mix";         // Colon-separated percentages for MovR txn types
constexpr char SH_ONLY[] = "sh_only";     // Force single-home transactions

// MovR specific parameters         
constexpr char MULTI_HOME_PCT[] = "multi_home_pct"; // Percentage of transactions that are multi-home (0-100)
constexpr char CONTENTION_FACTOR[] = "contention";  // Skew factor for record access (e.g., Zipf theta, 0 = uniform)
constexpr char REGION_REQUEST_MIX[] = "region_mix"; // Colon-separated percentages for request origins per region

// Default values for MovR parameters
const RawParamMap DEFAULT_PARAMS =
  {{PARTITION, "-1"},
  {HOMES, "2"},
  {MH_ZIPF, "0"},
  {TXN_MIX, "40:5:5:30:15:5"}, // Example Mix: ViewVehicles: 40%, UserSignup: 5%, AddVehicle: 5%, StartRide: 30%, UpdateLocation: 15%, EndRide: 5%
  {SH_ONLY, "0"},
  {MULTI_HOME_PCT, "10"},      // Default 10% multi-home transactions
  {CONTENTION_FACTOR, "0.0"},  // Default uniform access (no contention)
  {REGION_REQUEST_MIX, ""}};   // Default empty (implies uniform distribution or based on config)

// ID generation constants from data loader
constexpr int kPartitionBits = 16;
constexpr int kMaxUsersPerCity = kDefaultUsers / kDefaultCities;
constexpr int kMaxVehiclesPerCity = kDefaultVehicles / kDefaultCities;
constexpr int kMaxRidesPerCity = kDefaultRides / kDefaultCities;

// Counters (for debugging/logging)
int view_vehicle_count = 0;
int user_signup_count = 0;
int add_vehicle_count = 0;
int start_ride_count = 0;
int update_location_count = 0;
int end_ride_count = 0;
int total_txn_count = 0;
int multi_home_count = 0;

// Helper: Get number of regions (copied from TPCC)
int GetNumRegions(const ConfigurationPtr& config) {
  return config->num_regions() == 1 ? config->num_replicas(config->local_region()) : config->num_regions();
}

uint64_t GenerateGlobalId(int city_index, uint64_t local_id) {
  return (static_cast<uint64_t>(city_index) << (64 - kPartitionBits)) | (local_id & ((1ULL << (64 - kPartitionBits)) - 1));
}

int GetCityIndex(const string& city) {
  return std::stoi(city.substr(5)); // Extract index from "city_N"
}

vector<string> GetPartitionCities(int partition, const ConfigurationPtr& config) {
  vector<string> cities;
  int num_partitions = config->num_partitions();
  for (int i = 0; i < config->proto_config().movr_partitioning().cities(); i++) {
    if (i % num_partitions == partition) {
      cities.push_back("city_" + std::to_string(i));
    }
  }
  return cities;
}

} // namespace

MovrWorkload::MovrWorkload(const ConfigurationPtr& config, RegionId region, ReplicaId replica, const string& params_str,
                           std::pair<int, int> id_slot, const uint32_t seed)
    : Workload(DEFAULT_PARAMS, params_str),
      config_(config),
      local_region_(region),
      local_replica_(replica),
      distance_ranking_(config->distance_ranking_from(region)),
      rg_(seed),
      client_txn_id_counter_(0),
      cities_(GetPartitionCities(config->local_partition(), config)) {
  name_ = "movr";

  // Initialise parameters
  zipf_coef_ = params_.GetDouble(MH_ZIPF);
  multi_home_pct_ = params_.GetInt32(MULTI_HOME_PCT);
  contention_factor_ = params_.GetDouble(CONTENTION_FACTOR);
  sh_only_ = params_.GetInt32(SH_ONLY) == 1;

  // Setup region information and distance ranking
  num_regions_ = GetNumRegions(config_);
  if (distance_ranking_.empty()) {
    for (int i = 0; i < num_regions_; i++) {
      if (i != local_region_) {
        distance_ranking_.push_back(i);
      }
    }
    if (zipf_coef_ > 0) {
      LOG(WARNING) << "Distance ranking is not provided. MH_ZIPF is reset to 0.";
      zipf_coef_ = 0;
    }
  } else if (config_->num_regions() == 1) {
    // This case is for the Calvin experiment where there is only a single region.
    // The num_regions variable is equal to num_replicas at this point
    CHECK_EQ(static_cast<int>(distance_ranking_.size()), num_regions_ * (num_regions_ - 1));
    size_t from = local_region_ * (num_regions_ - 1);
    std::copy_n(distance_ranking_.begin() + from, num_regions_ - 1, distance_ranking_.begin());
    distance_ranking_.resize(num_regions_ - 1);
  }
  CHECK_EQ(static_cast<int>(distance_ranking_.size()), num_regions_ - 1) << "Distance ranking size must match the number of regions";

  // Validate and initialize distributions
  multi_home_dist_ = bernoulli_distribution(multi_home_pct_ / 100.0);
  InitializeTxnMix();
  InitializeRegionSelection();
}

void MovrWorkload::InitializeTxnMix() {
  auto txn_mix_str = Split(params_.GetString(TXN_MIX), ":");
  CHECK_EQ(txn_mix_str.size(), static_cast<size_t>(MovrTxnType::NUM_TXN_TYPES))
      << "Invalid transaction mix configuration";
  
  vector<double> mix_weights;
  int total = 0;
  for (const auto& pct : txn_mix_str) {
    int val = std::stoi(Trim(pct));
    mix_weights.push_back(val);
    total += val;
  }
  CHECK_EQ(total, 100) << "Transaction mix must sum to 100%";
  select_txn_dist_ = std::discrete_distribution<>(mix_weights.begin(), mix_weights.end());
}

void MovrWorkload::InitializeRegionSelection() {
  num_regions_ = GetNumRegions(config_);
  if (!params_.GetString(REGION_REQUEST_MIX).empty()) {
    // Parse custom region distribution
    auto region_pct = Split(params_.GetString(REGION_REQUEST_MIX), ":");
    CHECK_EQ(region_pct.size(), num_regions_) << "Region mix must match number of regions";
    
    vector<double> region_weights;
    int total = 0;
    for (const auto& pct : region_pct) {
      int val = std::stoi(Trim(pct));
      region_weights.push_back(val);
      total += val;
    }
    CHECK_EQ(total, 100) << "Region mix must sum to 100%";
    select_origin_region_dist_ = std::discrete_distribution<>(region_weights.begin(), region_weights.end());
  } else {
    // Uniform distribution
    vector<double> uniform_weights(num_regions_, 1.0/num_regions_);
    select_origin_region_dist_ = std::discrete_distribution<>(uniform_weights.begin(), uniform_weights.end());
  }
}

// Selects a home city based on the configured region mix
std::string MovrWorkload::SelectHomeCity() {
  if (cities_.empty()) {
    LOG(FATAL) << "No cities available in partition";
  }
  
  // Select based on region distribution
  int region_idx = select_origin_region_dist_(rg_);
  int city_idx = region_idx % cities_.size();
  return cities_[city_idx];
}

std::string MovrWorkload::SelectRemoteCity() {
  vector<int> remote_regions;
  for (int i = 0; i < num_regions_; i++) {
    if (i != local_region_) remote_regions.push_back(i);
  }
  
  int selected_region = zipf_sample(rg_, zipf_coef_, remote_regions, 1)[0];
  return "city_" + std::to_string(selected_region % config_->proto_config().movr_partitioning().cities());
}

std::pair<Transaction*, TransactionProfile> MovrWorkload::NextTransaction() {
  Transaction* txn = new Transaction();
  TransactionProfile pro;

  pro.client_txn_id = client_txn_id_counter_;
  pro.is_multi_home = false;

  // Determine if this transaction should be multi-home
  bool is_multi_home = !sh_only_ && multi_home_dist_(rg_);
  pro.is_multi_home = is_multi_home;
  if (is_multi_home) {
      multi_home_count++;
  }

  // Select the transaction type
  MovrTxnType txn_type = static_cast<MovrTxnType>(select_txn_dist_(rg_));
  string home_city = SelectHomeCity();

  switch (txn_type) {
    case MovrTxnType::VIEW_VEHICLES:
      GenerateViewVehiclesTxn(*txn, pro, home_city);
      view_vehicle_count++;
      break;
    case MovrTxnType::USER_SIGNUP:
      GenerateUserSignupTxn(*txn, pro, home_city);
      user_signup_count++;
      break;
    case MovrTxnType::ADD_VEHICLE:
      GenerateAddVehicleTxn(*txn, pro, home_city, is_multi_home);
      add_vehicle_count++;
      break;
    case MovrTxnType::START_RIDE:
      GenerateStartRideTxn(*txn, pro, home_city, is_multi_home);
      start_ride_count++;
      break;
    case MovrTxnType::UPDATE_LOCATION:
      GenerateUpdateLocationTxn(*txn, pro, home_city);
      update_location_count++;
      break;
    case MovrTxnType::END_RIDE:
      GenerateEndRideTxn(*txn, pro, home_city, is_multi_home);
      end_ride_count++;
      break;
    default:
      LOG(FATAL) << "Invalid MovR txn type selected";
  }

  total_txn_count++;

  txn->mutable_internal()->set_id(client_txn_id_counter_);
  client_txn_id_counter_++;

  LogStatistics();
  return {txn, pro};
}

// Logging for transaction counts/percentages
void MovrWorkload::LogStatistics() {
  if (total_txn_count % 10000 == 0) {
    LOG(INFO) << "MovR Stats - Total: " << total_txn_count
              << " ViewVehicles: " << view_vehicle_count
              << " UserSignups: " << user_signup_count
              << " AddVehicle: " << add_vehicle_count
              << " StartRide: " << start_ride_count
              << " UpdateLoc: " << update_location_count
              << " EndRide: " << end_ride_count
              << " MH%: " << (100.0 * multi_home_count / total_txn_count);
  }
}

// --- Transaction Generation Implementations --- 

// Simple read transaction: Find vehicles near a location in the specified city.
// This transaction is typically single-home, focused on the 'city'.
void MovrWorkload::GenerateViewVehiclesTxn(Transaction& txn, TransactionProfile& pro, const std::string& city) {
  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("view_vehicles");
  procedure->add_args(city);

  std::uniform_int_distribution<uint64_t> vehicle_dist(1, kMaxVehiclesPerCity);
  for (int i = 0; i < movr::kVehicleViewLimit; i++) {
    uint64_t local_id = vehicle_dist(rg_);
    uint64_t global_id = GenerateGlobalId(GetCityIndex(city), local_id);
    procedure->add_args(std::to_string(global_id));
  }
}

// Write transaction: Insert a new user record.
// This transaction is typically single-home, writing to the 'city' where the user signs up.
void MovrWorkload::GenerateUserSignupTxn(Transaction& txn, TransactionProfile& pro, const std::string& city) {
  uint64_t local_id = ++user_signup_count; // Simple sequential ID
  uint64_t global_id = GenerateGlobalId(GetCityIndex(city), local_id);

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("user_signup");
  procedure->add_args(std::to_string(global_id));
  procedure->add_args(city);
  procedure->add_args(DataGenerator::GenerateName(rg_));
  procedure->add_args(DataGenerator::GenerateAddress(rg_));
  procedure->add_args(DataGenerator::GenerateCreditCard(rg_));
}

// Write transaction: Add a new vehicle owned by a user.
// Can be multi-home if the owner (user) is in a different city than the vehicle's home city.
void MovrWorkload::GenerateAddVehicleTxn(Transaction& txn, TransactionProfile& pro, const std::string& home_city, bool is_multi_home) {
  std::string owner_city = home_city;
  if (is_multi_home) {
      owner_city = SelectRemoteCity();
  }

  uint64_t vehicle_local_id = ++add_vehicle_count;
  uint64_t vehicle_id = GenerateGlobalId(GetCityIndex(home_city), vehicle_local_id);
  
  uint64_t owner_local_id = std::uniform_int_distribution<>(1, kMaxUsersPerCity)(rg_);
  uint64_t owner_id = GenerateGlobalId(GetCityIndex(owner_city), owner_local_id);

  const std::string type = DataGenerator::GenerateRandomVehicleType(rg_);

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("add_vehicle");
  procedure->add_args(std::to_string(vehicle_id));
  procedure->add_args(home_city);
  procedure->add_args(type);
  procedure->add_args(std::to_string(owner_id));
  procedure->add_args(owner_city);
  procedure->add_args(std::to_string(std::chrono::system_clock::now().time_since_epoch().count()));
  procedure->add_args("available");
  procedure->add_args(DataGenerator::GenerateAddress(rg_));
  procedure->add_args(DataGenerator::GenerateVehicleMetadata(rg_, type));
}

// Read/Write transaction: A user starts a ride on a vehicle.
// Reads user info, vehicle status. Writes new ride record, updates vehicle status.
// Can be multi-home if the user is in a different city than the vehicle.
void MovrWorkload::GenerateStartRideTxn(Transaction& txn, TransactionProfile& pro, const std::string& home_city, bool is_multi_home) {
  std::string user_city = home_city;
  std::string vehicle_city = home_city; // Link to actual vehicle city
  //std::string code = DataGenerator::GeneratePromoCode(rg_);
  if (is_multi_home) {
      // 50% chance vehicle is remote, 50% chance user is remote
      if (std::bernoulli_distribution(0.5)(rg_)) { 
          user_city = SelectRemoteCity();
      } else {
          vehicle_city = SelectRemoteCity();
      }
  }

  // Generate IDs within valid ranges
  uint64_t user_local_id = std::uniform_int_distribution<>(1, kMaxUsersPerCity)(rg_);
  uint64_t vehicle_local_id = std::uniform_int_distribution<>(1, kMaxVehiclesPerCity)(rg_);
  uint64_t ride_local_id = ++start_ride_count;
  
  uint64_t user_id = GenerateGlobalId(GetCityIndex(user_city), user_local_id);
  uint64_t vehicle_id = GenerateGlobalId(GetCityIndex(vehicle_city), vehicle_local_id);
  uint64_t ride_id = GenerateGlobalId(GetCityIndex(home_city), ride_local_id);

  // const std::string user_id = DataGenerator::GenerateContendedID(rg_, contention_factor_, 1000); // Link to actual existing user id
  // const std::string vehicle_id = DataGenerator::GenerateContendedID(rg_, contention_factor_, 1000); // Link to actual existing vehicle id
  
  // const std::string ride_id = DataGenerator::GenerateUUID(rg_);
  // const std::string start_address = DataGenerator::GenerateAddress(rg_);
  // const std::string start_time = std::to_string(
  //   std::chrono::system_clock::now().time_since_epoch().count());

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("start_ride");
  procedure->add_args(std::to_string(user_id));
  procedure->add_args(user_city);
  procedure->add_args(DataGenerator::GeneratePromoCode(rg_));
  procedure->add_args(std::to_string(vehicle_id));
  procedure->add_args(vehicle_city);
  procedure->add_args(std::to_string(ride_id));
  procedure->add_args(home_city);
  procedure->add_args(DataGenerator::GenerateAddress(rg_));
  procedure->add_args(std::to_string(std::chrono::system_clock::now().time_since_epoch().count()));
}

// Write transaction: Append a location update to a ride's history.
// Typically single-home, writing to the city where the ride is happening.
void MovrWorkload::GenerateUpdateLocationTxn(Transaction& txn, TransactionProfile& pro, const std::string& city) {
  uint64_t ride_local_id = std::uniform_int_distribution<>(1, kMaxRidesPerCity)(rg_);
  uint64_t ride_id = GenerateGlobalId(GetCityIndex(city), ride_local_id);

  // const std::string ride_id = DataGenerator::GenerateUUID(rg_); // Link to an actual active ride
  // const std::string timestamp = std::to_string(
  //   std::chrono::system_clock::now().time_since_epoch().count());
  
  // const std::string lat = loc.first;
  // const std::string lon = loc.second;

  const auto loc = DataGenerator::GenerateRandomLatLong(rg_);
  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("update_location");
  procedure->add_args(city);
  procedure->add_args(std::to_string(ride_id));
  procedure->add_args(std::to_string(std::chrono::system_clock::now().time_since_epoch().count()));
  procedure->add_args(loc.first);
  procedure->add_args(loc.second);
}

// Read/Write transaction: End a ride, update vehicle status, calculate revenue.
// Reads ride info, vehicle info. Updates ride record, updates vehicle status.
// Can be multi-home if the ride spanned cities or user/vehicle are in different cities.
void MovrWorkload::GenerateEndRideTxn(Transaction& txn, TransactionProfile& pro, const std::string& home_city, bool is_multi_home) {
  std::string user_city = home_city;
  std::string vehicle_city = home_city;

  if (is_multi_home) {
    // 50% chance vehicle is from remote city
    if (std::bernoulli_distribution(0.5)(rg_)) { 
        vehicle_city = SelectRemoteCity();
    }
  }

  uint64_t ride_local_id = std::uniform_int_distribution<>(1, kMaxRidesPerCity)(rg_);
  uint64_t user_local_id = std::uniform_int_distribution<>(1, kMaxUsersPerCity)(rg_);
  uint64_t vehicle_local_id = std::uniform_int_distribution<>(1, kMaxVehiclesPerCity)(rg_);
  
  uint64_t ride_id = GenerateGlobalId(GetCityIndex(home_city), ride_local_id);
  uint64_t user_id = GenerateGlobalId(GetCityIndex(user_city), user_local_id);
  uint64_t vehicle_id = GenerateGlobalId(GetCityIndex(vehicle_city), vehicle_local_id);

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("end_ride");
  procedure->add_args(std::to_string(ride_id));
  procedure->add_args(home_city);
  procedure->add_args(std::to_string(vehicle_id));
  procedure->add_args(vehicle_city);
  // procedure->add_args(std::to_string(user_id)); // ???
  procedure->add_args(user_city);
  procedure->add_args(DataGenerator::GenerateAddress(rg_));
  procedure->add_args(std::to_string(std::chrono::system_clock::now().time_since_epoch().count()));
  procedure->add_args(DataGenerator::GenerateRevenue(rg_));
}

} // namespace slog