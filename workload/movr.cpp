#include "workload/movr.h"

#include <glog/logging.h>

#include <random>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#include "common/proto_utils.h"
#include "common/string_utils.h"
#include "execution/movr/constants.h"
#include "execution/movr/transaction.h"

using std::bernoulli_distribution;
using std::iota;
using std::sample;
using std::string;
using std::stringstream;
using std::to_string;
using std::unordered_set;
using std::vector;

namespace slog {
namespace {

// Existing parameters (copied from TPCC)
constexpr char PARTITION[] = "partition"; // Use specific partition, -1 for random
constexpr char HOMES[] = "homes";         // Max number of regions accessed in a multi-home txn
constexpr char MH_ZIPF[] = "mh_zipf";     // Zipf coefficient for selecting remote regions
constexpr char TXN_MIX[] = "mix";         // Colon-separated percentages for MovR txn types
constexpr char SH_ONLY[] = "sh_only";     // Force single-home transactions

// MovR specific parameters
constexpr char CITIES[] = "cities";                 // Comma-separated list of cities to use
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
  {CITIES, "amsterdam,boston,new york,paris,rome"},
  {MULTI_HOME_PCT, "10"},      // Default 10% multi-home transactions
  {CONTENTION_FACTOR, "0.0"},  // Default uniform access (no contention)
  {REGION_REQUEST_MIX, ""}};   // Default empty (implies uniform distribution or based on config)

// Counters (for debugging/logging)
int view_vehicle_count = 0;
int user_signup_count = 0;
int add_vehicle_count = 0;
int start_ride_count = 0;
int update_location_count = 0;
int end_ride_count = 0;
int total_txn_count = 0;
int multi_home_count = 0;

// Helper: Sample one element randomly (copied from TPCC)
template <typename T, typename G>
T SampleOnce(G& g, const std::vector<T>& source) {
  CHECK(!source.empty());
  size_t i = std::uniform_int_distribution<size_t>(0, source.size() - 1)(g);
  return source[i];
}

// Helper: Get number of regions (copied from TPCC)
int GetNumRegions(const ConfigurationPtr& config) {
  return config->num_regions() == 1 ? config->num_replicas(config->local_region()) : config->num_regions();
}

}  // namespace

// Namespace for data generation functions
namespace generator {

  template <typename T>
  T WeightedChoice(std::mt19937& rng, const std::vector<std::pair<T, double>>& items) {
    double total_weight = 0.0;
    for (const auto& item : items) total_weight += item.second;

    std::uniform_real_distribution<double> dist(0.0, total_weight);
    double n = dist(rng);

    for (const auto& [value, weight] : items) {
      if (n < weight) return value;
      n -= weight;
    }

    return items.back().first; // fallback in case of rounding errors
  }

  inline std::string GenerateUUID(std::mt19937& rng) {
    std::uniform_int_distribution<int> dist(0, 15);
    std::uniform_int_distribution<int> dist2(8, 11); // variant field
  
    std::stringstream ss;
    ss << std::hex;
  
    for (int i = 0; i < 8; i++) ss << dist(rng);
    ss << "-";
    for (int i = 0; i < 4; i++) ss << dist(rng);
    ss << "-4"; // UUID version 4
    for (int i = 0; i < 3; i++) ss << dist(rng);
    ss << "-";
    ss << dist2(rng); // UUID variant
    for (int i = 0; i < 3; i++) ss << dist(rng);
    ss << "-";
    for (int i = 0; i < 12; i++) ss << dist(rng);
  
    return ss.str();
  }

  inline std::string GenerateRevenue(std::mt19937& rng) {
    std::uniform_real_distribution<double> dist(1.0, 100.0);
    std::stringstream ss;
    ss << std::fixed << std::setprecision(2) << dist(rng);
    return ss.str();
}

  inline std::string GenerateRandomVehicleType(std::mt19937& rng) {
    static const std::vector<std::string> types = {"skateboard", "bike", "scooter"};
    std::uniform_int_distribution<> dist(0, types.size() - 1);
    return types[dist(rng)];
  }

  inline std::string GetVehicleAvailability(std::mt19937& rng) {
    static const std::vector<std::pair<std::string, double>> choices = {
      {"available", 0.4}, {"in_use", 0.55}, {"lost", 0.05}
    };
    return WeightedChoice(rng, choices);
  }

  inline std::string GenerateRandomColor(std::mt19937& rng) {
    static const std::vector<std::string> colors = {"red", "yellow", "blue", "green", "black"};
    std::uniform_int_distribution<> dist(0, colors.size() - 1);
    return colors[dist(rng)];
  }

  inline std::pair<std::string, std::string> GenerateRandomLatLong(std::mt19937& rng) {
    std::uniform_real_distribution<double> lat_dist(-90.0, 90.0);
    std::uniform_real_distribution<double> lon_dist(-180.0, 180.0);
    std::stringstream ss_lat, ss_lon;
    ss_lat << std::fixed << std::setprecision(6) << lat_dist(rng);
    ss_lon << std::fixed << std::setprecision(6) << lon_dist(rng);
    return {ss_lat.str(), ss_lon.str()};
  }

  inline std::string GenerateBikeBrand(std::mt19937& rng) {
    static const std::vector<std::string> brands = {
      "Merida", "Fuji", "Cervelo", "Pinarello", "Santa Cruz", "Kona", "Schwinn"
    };
    std::uniform_int_distribution<> dist(0, brands.size() - 1);
    return brands[dist(rng)];
  }

  inline std::string GenerateVehicleMetadata(std::mt19937& rng, const std::string& type) {
    std::string color = GenerateRandomColor(rng);
    std::string brand = (type == "bike") ? GenerateBikeBrand(rng) : "";

    // Simple JSON-like string
    std::string result = "{\"color\": \"" + color + "\"";
    if (!brand.empty()) {
      result += ", \"brand\": \"" + brand + "\"";
    }
    result += "}";
    return result;
  }

  inline std::string GenerateName(std::mt19937& rng) {
    static const std::vector<std::string> first_names = {
        "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", 
        "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", 
        "Barbara", "Susan", "Jessica", "Sarah", "Karen"
    };
    
    static const std::vector<std::string> last_names = {
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", 
        "Garcia", "Rodriguez", "Wilson", "Martinez", "Anderson", "Taylor", 
        "Thomas", "Hernandez", "Moore", "Martin", "Jackson", "Thompson", "White"
    };
    
    std::uniform_int_distribution<size_t> first_dist(0, first_names.size() - 1);
    std::uniform_int_distribution<size_t> last_dist(0, last_names.size() - 1);
    
    return first_names[first_dist(rng)] + " " + last_names[last_dist(rng)];
  }

  inline std::string GenerateAddress(std::mt19937& rng) {
    static const std::vector<std::string> street_names = {
      "Main", "Oak", "Pine", "Maple", "Cedar", "Elm", "View",
      "Washington", "Lake", "Hill", "Park", "Sunset", "Highland",
      "Railroad", "Church", "Willow", "Meadow", "Broad", "Forest", "River"};

    static const std::vector<std::string> street_suffixes = {
      "St", "Ave", "Blvd", "Rd", "Ln", "Dr", "Ct", "Pl", "Cir", "Way"};

    std::uniform_int_distribution<int> house_num_dist(100, 9999);
    std::uniform_int_distribution<size_t> street_dist(0, street_names.size() - 1);
    std::uniform_int_distribution<size_t> suffix_dist(0, street_suffixes.size() - 1);
    return std::to_string(house_num_dist(rng)) + " " + street_names[street_dist(rng)] + " " + street_suffixes[suffix_dist(rng)];
  }

  inline std::string GenerateCreditCard(std::mt19937& rng) {
    std::string number;
    std::uniform_int_distribution<int> digit_dist(0, 9);
    
    for (int i = 0; i < 16; i++) {
        if (i > 0 && i % 4 == 0) {
            number += " ";
        }
        number += std::to_string(digit_dist(rng));
    }
    return number;
  }

  inline std::string GeneratePromoCode(std::mt19937& rng) {
    static const std::vector<std::string> words = {
      "free", "summer", "discount", "save", "code", "quick",
      "deal", "offer", "special", "limited", "bonus", "credit",
      "voucher", "gift", "reward", "holiday", "welcome", "newuser"
    };
    std::uniform_int_distribution<size_t> word_dist(0, words.size() - 1);
    return words[word_dist(rng)] + "_" + words[word_dist(rng)] + "_" + words[word_dist(rng)];
  }

  // Function to generate a potentially contended ID based on contention_factor_
  inline std::string GenerateContendedID(std::mt19937& rng, double contention_factor, int max_id) {
    if (contention_factor <= 0.0 || max_id <= 1) { // Uniform distribution if no contention or not enough items
        std::uniform_int_distribution<> dist(1, max_id);
        return std::to_string(dist(rng));
    }
    
    // Simple Zipfian-like selection
    std::vector<int> ids(max_id);
    std::iota(ids.begin(), ids.end(), 1);
    auto sampled_ids = zipf_sample(rng, contention_factor, ids, 1);
    return std::to_string(sampled_ids[0]);
  }
} // namespace generator

MovrWorkload::MovrWorkload(const ConfigurationPtr& config, RegionId region, ReplicaId replica, const string& params_str,
                           std::pair<int, int> id_slot, const uint32_t seed)
    : Workload(DEFAULT_PARAMS, params_str),
      config_(config),
      local_region_(region),
      local_replica_(replica),
      distance_ranking_(config->distance_ranking_from(region)),
      rg_(seed),
      client_txn_id_counter_(0) {
  name_ = "movr";

  // Parse parameters
  zipf_coef_ = params_.GetDouble(MH_ZIPF);
  multi_home_pct_ = params_.GetInt32(MULTI_HOME_PCT);
  contention_factor_ = params_.GetDouble(CONTENTION_FACTOR);
  sh_only_ = params_.GetInt32(SH_ONLY) == 1;

  // Validate multi_home_pct
  if (multi_home_pct_ < 0 || multi_home_pct_ > 100) {
      LOG(FATAL) << "Invalid multi_home_pct: " << multi_home_pct_ << ". Must be between 0 and 100.";
  }
  multi_home_dist_ = std::bernoulli_distribution(multi_home_pct_ / 100.0);

  // Parse cities
  auto city_names = Split(params_.GetString(CITIES), ",");
  CHECK(!city_names.empty()) << "No cities specified in parameters.";
  for(const auto& city_name : city_names) {
      cities_.push_back(Trim(city_name));
  }
  num_cities_ = cities_.size();
  CHECK_EQ(num_cities_, config->proto_config().movr_partitioning().cities_size());

  // Parse transaction mix
  auto txn_mix_str = Split(params_.GetString(TXN_MIX), ":");
  CHECK_EQ(txn_mix_str.size(), static_cast<size_t>(MovrTxnType::NUM_TXN_TYPES))
      << "Invalid number of values for MovR txn mix. Expected "
      << static_cast<int>(MovrTxnType::NUM_TXN_TYPES);
  int total_mix_pct = 0;
  for (const auto& t : txn_mix_str) {
    int pct = std::stoi(Trim(t));
    CHECK(pct >= 0) << "Transaction mix percentages must be non-negative.";
    txn_mix_pct_.push_back(pct);
    total_mix_pct += pct;
  }
  CHECK_EQ(total_mix_pct, 100) << "Transaction mix percentages must sum to 100.";
  select_txn_dist_ = std::discrete_distribution<>(txn_mix_pct_.begin(), txn_mix_pct_.end());

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

  // Parse region request mix
  auto region_mix_str = params_.GetString(REGION_REQUEST_MIX);
  if (!region_mix_str.empty()) {
      auto region_mix_pct_str = Split(region_mix_str, ":");
      CHECK_EQ(static_cast<int>(region_mix_pct_str.size()), num_regions_) << "Region mix must have percentages for all regions.";
      int total_region_pct = 0;
      for (const auto& pct_str : region_mix_pct_str) {
          int pct = std::stoi(Trim(pct_str));
          CHECK(pct >= 0) << "Region mix percentages must be non-negative.";
          region_request_pct_.push_back(pct);
          total_region_pct += pct;
      }
      CHECK_EQ(total_region_pct, 100) << "Region mix percentages must sum to 100.";
      select_origin_region_dist_ = std::discrete_distribution<>(region_request_pct_.begin(), region_request_pct_.end());
  } else {
      // Default to uniform distribution if no mix is provided
      std::vector<double> uniform_dist(num_regions_, 100.0 / num_regions_);
      select_origin_region_dist_ = std::discrete_distribution<>(uniform_dist.begin(), uniform_dist.end());
  }

  max_users_ = 10000; // Placeholder
  max_vehicles_ = 5000; // Placeholder
}

// Selects a home city based on the configured region mix
std::string MovrWorkload::SelectHomeCity() {
  // Determine the origin region based on the distribution
  int origin_region_idx = select_origin_region_dist_(rg_);
  
  // Map the region index to a city (this mapping needs to be defined based on config)
  // Assume cities are distributed round-robin across regions
  if (cities_.empty()) {
      LOG(FATAL) << "No cities available to select from.";
      return ""; // Should not happen due to CHECK in constructor
  }
  int city_idx = origin_region_idx % cities_.size();
  return cities_[city_idx];
}

// Selects a remote city, potentially based on distance ranking and Zipf distribution
std::string MovrWorkload::SelectRemoteCity(const std::string& home_city) {
  if (num_regions_ <= 1 || distance_ranking_.empty()) {
      return home_city; // Cannot select a remote city
  }

  int home_region_idx = local_region_; // Placeholder: Assume home_city is in local_region_

  // Select a remote region index based on distance ranking and zipf coefficient
  std::vector<int> remote_region_indices;
  if (zipf_coef_ > 0) {
      remote_region_indices = zipf_sample(rg_, zipf_coef_, distance_ranking_, 1);
  } else {
      // Uniform selection from other regions
      std::uniform_int_distribution<size_t> dist(0, distance_ranking_.size() - 1);
      remote_region_indices.push_back(distance_ranking_[dist(rg_)]);
  }
  int remote_region_idx = remote_region_indices[0];

  // Map the remote region index to a city (requires mapping)
  // Simple example: Assume cities are distributed round-robin across regions
  int remote_city_idx = remote_region_idx % cities_.size(); // Very basic mapping
  return cities_[remote_city_idx];
}

std::pair<Transaction*, TransactionProfile> MovrWorkload::NextTransaction() {
  Transaction* txn = new Transaction();
  TransactionProfile pro;

  pro.client_txn_id = client_txn_id_counter_;
  pro.is_multi_home = false;

  // Determine if this transaction should be multi-home
  bool is_multi_home_txn = false;
  if (!sh_only_ && num_regions_ > 1) {
      is_multi_home_txn = multi_home_dist_(rg_);
  }
  pro.is_multi_home = is_multi_home_txn;
  if (is_multi_home_txn) {
      multi_home_count++;
  }

  // Select the home city for the transaction based on regional mix
  std::string home_city = SelectHomeCity();

  // Select the transaction type
  MovrTxnType txn_type = static_cast<MovrTxnType>(select_txn_dist_(rg_));

  // Generate transaction based on type
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
      GenerateAddVehicleTxn(*txn, pro, home_city, is_multi_home_txn);
      add_vehicle_count++;
      break;
    case MovrTxnType::START_RIDE:
      GenerateStartRideTxn(*txn, pro, home_city, is_multi_home_txn);
      start_ride_count++;
      break;
    case MovrTxnType::UPDATE_LOCATION:
      GenerateUpdateLocationTxn(*txn, pro, home_city);
      update_location_count++;
      break;
    case MovrTxnType::END_RIDE:
      GenerateEndRideTxn(*txn, pro, home_city, is_multi_home_txn);
      end_ride_count++;
      break;
    default:
      LOG(FATAL) << "Invalid MovR txn type selected";
  }

  total_txn_count++;
  // Logging for transaction counts/percentages
  if (total_txn_count % 10000 == 0) { // Log every 10k transactions
      LOG(INFO) << "MovR Txn Counts (Total: " << total_txn_count << ") - "
                << "ViewVehicles: " << view_vehicle_count << ", "
                << "UserSignup: " << user_signup_count << ", "
                << "AddVehicle: " << add_vehicle_count << ", "
                << "StartRide: " << start_ride_count << ", "
                << "UpdateLoc: " << update_location_count << ", "
                << "EndRide: " << end_ride_count << ". "
                << "Multi-Home: " << multi_home_count << " (" << (100.0 * multi_home_count / total_txn_count) << "%)";
  }

  txn->mutable_internal()->set_id(client_txn_id_counter_);
  client_txn_id_counter_++;

  return {txn, pro};
}

// --- Transaction Generation Implementations --- 

// Simple read transaction: Find vehicles near a location in the specified city.
// This transaction is typically single-home, focused on the 'city'.
void MovrWorkload::GenerateViewVehiclesTxn(Transaction& txn, TransactionProfile& pro, const std::string& city) {

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("view_vehicles");
  procedure->add_args(city);
  for (int i = 0; i < movr::kVehicleViewLimit; i++) {
    const std::string id = generator::GenerateContendedID(rg_, contention_factor_, max_users_);
    procedure->add_args(id);
  }
}

// Write transaction: Insert a new user record.
// This transaction is typically single-home, writing to the 'city' where the user signs up.
void MovrWorkload::GenerateUserSignupTxn(Transaction& txn, TransactionProfile& pro, const std::string& city) {
  const std::string user_id = generator::GenerateUUID(rg_);
  const std::string name = generator::GenerateName(rg_);
  const std::string address = generator::GenerateAddress(rg_);
  const std::string credit_card = generator::GenerateCreditCard(rg_);

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("user_signup");
  procedure->add_args(user_id);
  procedure->add_args(city);
  procedure->add_args(name);
  procedure->add_args(address);
  procedure->add_args(credit_card);
}

// Write transaction: Add a new vehicle owned by a user.
// Can be multi-home if the owner (user) is in a different city than the vehicle's home city.
void MovrWorkload::GenerateAddVehicleTxn(Transaction& txn, TransactionProfile& pro, const std::string& home_city, bool is_multi_home) {
  std::string owner_city = home_city;
  if (is_multi_home) {
      owner_city = SelectRemoteCity(home_city);
      pro.is_multi_home = true;
  } else {
      pro.is_multi_home = false;
  }

  // Generate potentially contended IDs based on contention_factor_
  const std::string owner_id = generator::GenerateContendedID(rg_, contention_factor_, max_users_); 
  const std::string vehicle_id = generator::GenerateContendedID(rg_, contention_factor_, max_vehicles_);

  const std::string type = generator::GenerateRandomVehicleType(rg_);
  const std::string creation_time = std::to_string(
    std::chrono::system_clock::now().time_since_epoch().count());
  const std::string status = "available"; // New vehicles start as available
  const std::string current_location = generator::GenerateAddress(rg_);
  const std::string ext = generator::GenerateVehicleMetadata(rg_, type);

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("add_vehicle");
  procedure->add_args(vehicle_id);
  procedure->add_args(home_city);
  procedure->add_args(type);
  procedure->add_args(owner_id);
  procedure->add_args(owner_city);
  procedure->add_args(creation_time);
  procedure->add_args(status);
  procedure->add_args(current_location);
  procedure->add_args(ext);
}

// Read/Write transaction: A user starts a ride on a vehicle.
// Reads user info, vehicle status. Writes new ride record, updates vehicle status.
// Can be multi-home if the user is in a different city than the vehicle.
void MovrWorkload::GenerateStartRideTxn(Transaction& txn, TransactionProfile& pro, const std::string& home_city, bool is_multi_home) {
  std::string user_city = home_city;
  std::string code = generator::GeneratePromoCode(rg_);
  std::string vehicle_city = home_city; // Link to actual vehicle city
  if (is_multi_home) {
      // Decide which entity is remote (user or vehicle)
      if (std::bernoulli_distribution(0.5)(rg_)) { // 50% chance user is remote
          user_city = SelectRemoteCity(home_city);
      } else { // Vehicle is remote
          vehicle_city = SelectRemoteCity(home_city);
      }
      pro.is_multi_home = true;
  } else {
      pro.is_multi_home = false;
  }

  // Generate potentially contended IDs
  const std::string user_id = generator::GenerateContendedID(rg_, contention_factor_, max_users_); // Link to actual existing user id
  const std::string vehicle_id = generator::GenerateContendedID(rg_, contention_factor_, max_vehicles_); // Link to actual existing vehicle id
  
  const std::string ride_id = generator::GenerateUUID(rg_);
  const std::string start_address = generator::GenerateAddress(rg_);
  const std::string start_time = std::to_string(
    std::chrono::system_clock::now().time_since_epoch().count());

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("start_ride");
  procedure->add_args(user_id);
  procedure->add_args(user_city);
  procedure->add_args(code);
  procedure->add_args(vehicle_id);
  procedure->add_args(vehicle_city);
  procedure->add_args(ride_id);
  procedure->add_args(home_city);
  procedure->add_args(start_address);
  procedure->add_args(start_time);
}

// Write transaction: Append a location update to a ride's history.
// Typically single-home, writing to the city where the ride is happening.
void MovrWorkload::GenerateUpdateLocationTxn(Transaction& txn, TransactionProfile& pro, const std::string& city) {
  const std::string ride_id = generator::GenerateUUID(rg_); // Link to an actual active ride
  const std::string timestamp = std::to_string(
    std::chrono::system_clock::now().time_since_epoch().count());
  const auto loc = generator::GenerateRandomLatLong(rg_);
  const std::string lat = loc.first;
  const std::string lon = loc.second;

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("update_location");
  procedure->add_args(city);
  procedure->add_args(ride_id);
  procedure->add_args(timestamp);
  procedure->add_args(lat);
  procedure->add_args(lon);
}

// Read/Write transaction: End a ride, update vehicle status, calculate revenue.
// Reads ride info, vehicle info. Updates ride record, updates vehicle status.
// Can be multi-home if the ride spanned cities or user/vehicle are in different cities.
void MovrWorkload::GenerateEndRideTxn(Transaction& txn, TransactionProfile& pro, const std::string& home_city, bool is_multi_home) {
  std::string user_city = home_city; // Assume user ends ride in their home city
  std::string vehicle_city = home_city; // Assume vehicle started in home_city

  const std::string ride_id = generator::GenerateUUID(rg_); // Link to an actual active ride
  const std::string vehicle_id = generator::GenerateUUID(rg_); // Link to an actual vehicle

  if (is_multi_home) {
    // Determine the vehicle's actual city (might need to be read from ride/vehicle record)
    // For simulation, randomly choose if the vehicle's origin was remote.
    if (std::bernoulli_distribution(0.5)(rg_)) { 
        vehicle_city = SelectRemoteCity(home_city);
    }
    pro.is_multi_home = true;
  } else {
    pro.is_multi_home = false;
  }

  const std::string end_address = generator::GenerateAddress(rg_);
  const std::string end_time = std::to_string(
    std::chrono::system_clock::now().time_since_epoch().count());
  const std::string revenue = generator::GenerateRevenue(rg_);

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("end_ride");
  procedure->add_args(ride_id);
  procedure->add_args(home_city);
  procedure->add_args(vehicle_id);
  procedure->add_args(vehicle_city);
  procedure->add_args(user_city);
  procedure->add_args(end_address);
  procedure->add_args(end_time);
  procedure->add_args(revenue);
}

}  // namespace slog