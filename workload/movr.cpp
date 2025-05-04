#include "workload/movr.h"

#include <glog/logging.h>

#include <random>
#include <set>

#include "common/proto_utils.h"
#include "execution/tpcc/constants.h"
#include "execution/tpcc/transaction.h"

using std::bernoulli_distribution;
using std::iota;
using std::sample;
using std::to_string;
using std::unordered_set;

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
    return std::to_string(dist(rng));
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
    return {
      std::to_string(lat_dist(rng)),
      std::to_string(lon_dist(rng))
    };
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
        "Main", "Oak", "Pine", "Maple", "Cedar", "Elm", "View", "Washington", 
        "Lake", "Hill", "Park", "Sunset", "Highland", "Railroad", "Church", 
        "Willow", "Meadow", "Broad", "Forest", "River"
    };
    
    static const std::vector<std::string> street_suffixes = {
        "St", "Ave", "Blvd", "Rd", "Ln", "Dr", "Ct", "Pl", "Cir", "Way"
    };
    
    static const std::vector<std::string> cities = {
        "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", 
        "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville", 
        "San Francisco", "Columbus", "Charlotte", "Indianapolis", "Seattle", "Denver", 
        "Washington", "Boston"
    };
    
    static const std::vector<std::string> states = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
    };
    
    std::uniform_int_distribution<int> house_num_dist(100, 9999);
    std::uniform_int_distribution<size_t> street_dist(0, street_names.size() - 1);
    std::uniform_int_distribution<size_t> suffix_dist(0, street_suffixes.size() - 1);
    std::uniform_int_distribution<size_t> city_dist(0, cities.size() - 1);
    std::uniform_int_distribution<size_t> state_dist(0, states.size() - 1);
    std::uniform_int_distribution<int> zip_dist(10000, 99999);
    
    return std::to_string(house_num_dist(rng)) + " " + 
           street_names[street_dist(rng)] + " " + 
           street_suffixes[suffix_dist(rng)] + ", " + 
           cities[city_dist(rng)] + ", " + 
           states[state_dist(rng)] + " " + 
           std::to_string(zip_dist(rng));
  }
  std::string GenerateCreditCard(std::mt19937& rng) {
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
} // namespace generator

MovrWorkload::MovrWorkload(const ConfigurationPtr& config, RegionId region, ReplicaId replica, const string& params_str,
                           std::pair<int, int> id_slot, const uint32_t seed)
    : Workload(DEFAULT_PARAMS, params_str),
      config_(config),
      local_region_(region),
      local_replica_(replica),
      distance_ranking_(config->distance_ranking_from(region)),
      zipf_coef_(params_.GetInt32(MH_ZIPF)),
      rg_(seed),
      client_txn_id_counter_(0) {
  name_ = "movr";
  // Access and validate movr_partitioning
  CHECK(config_->proto_config().has_movr_partitioning()) << "MOVR workload requires movr_partitioning block in config.";

  const auto& movr_part = config_->proto_config().movr_partitioning();
  for (const auto& city : movr_part.cities()) {
    cities_.push_back(city);
  }
  CHECK(!cities_.empty()) << "City list in movr_partitioning is empty";

  auto num_regions = GetNumRegions(config_);
  if (distance_ranking_.empty()) {
    for (int i = 0; i < num_regions; i++) {
      if (i != local_region()) {
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
    CHECK_EQ(distance_ranking_.size(), num_regions * (num_regions - 1));
    size_t from = local_region() * (num_regions - 1);
    std::copy_n(distance_ranking_.begin() + from, num_regions, distance_ranking_.begin());
    distance_ranking_.resize(num_regions - 1);
  }

  CHECK_EQ(distance_ranking_.size(), num_regions - 1) << "Distance ranking size must match the number of regions";

  auto num_partitions = config_->num_partitions();
  for (int i = 0; i < num_partitions; i++) {
    vector<vector<int>> partitions(num_regions);
  }

  auto txn_mix_str = Split(params_.GetString(TXN_MIX), ":");
  CHECK_EQ(txn_mix_str.size(), 6) << "There must be exactly 6 values for txn mix";
  for (const auto& t : txn_mix_str) {
    txn_mix_.push_back(std::stoi(t));
  }
}

std::pair<Transaction*, TransactionProfile> MovrWorkload::NextTransaction() {
  //LOG(INFO) << "Creating next TPCC transaction";
  TransactionProfile pro;

  pro.client_txn_id = client_txn_id_counter_;
  pro.is_multi_partition = false;
  pro.is_multi_home = false;
  pro.is_foreign_single_home = false;

  auto num_partitions = config_->num_partitions();
  auto partition = params_.GetInt32(PARTITION);
  if (partition < 0) {
    partition = std::uniform_int_distribution<>(0, num_partitions - 1)(rg_);
  }

  const auto& selectable_w = warehouse_index_[partition][local_region()];
  CHECK(!selectable_w.empty()) << "Not enough warehouses";
  int w = SampleOnce(rg_, selectable_w);

  Transaction* txn = new Transaction();
  std::discrete_distribution<> select_movr_txn(txn_mix_.begin(), txn_mix_.end());
  switch (select_movr_txn(rg_)) {
    case 0:
      GenerateViewVehiclesTxn(*txn, pro);
      view_vehicle_count++;
      break;
    case 1:
      GenerateUserSignupTxn(*txn, pro);
      user_signup_count++;
      break;
    case 2:
      GenerateAddVehicleTxn(*txn, pro);
      add_vehicle_count++;
      break;
    case 3:
      GenerateStartRideTxn(*txn, pro);
      start_ride_count++;
      break;
    case 4:
      GenerateUpdateLocationTxn(*txn, pro);
      update_location_count++;
      break;
    case 5:
      GenerateEndRideTxn(*txn, pro);
      end_ride_count++;
      break;
    default:
      LOG(FATAL) << "Invalid txn choice";
  }
  total_txn_count++;
  if (total_txn_count % 100000 == 0) {
    LOG(INFO) << "Current SH txn counts: Total: " << total_txn_count << " NO: " << new_order_count << " P: "<< payment_count << " OS: " << order_status_count << " D: "<< delivery_count << " SL: "<< stock_level_count;
    LOG(INFO) << "Current FSH txn counts: Total: " << total_txn_count << " NO: " << fsh_no << " P: " << fsh_pay << " OS: " << fsh_os << " D: " << fsh_del << " SL: "<< fsh_sl;
    LOG(INFO) << "Current MH txn counts: Total: " << total_txn_count << " NO: " << mh_no << " P: " << mh_pay << " OS: " << mh_os << " D: " << mh_del << " SL: "<< mh_sl;
    LOG(INFO) << "Current SH txn percentages: NO: " << 100*new_order_count/(double)total_txn_count << " P: " << 100*payment_count/(double)total_txn_count << " OS: " << 100*order_status_count/(double)total_txn_count << " D: " << 100*delivery_count/(double)total_txn_count << " SL: " << 100*stock_level_count/(double)total_txn_count;
    LOG(INFO) << "Current FSH txn percentages: NO: " << 100*fsh_no/(double)total_txn_count << " P: " << 100*fsh_pay/(double)total_txn_count << " OS: " << 100*fsh_os/(double)total_txn_count << " D: " << 100*fsh_del/(double)total_txn_count << " SL: " << 100*fsh_sl/(double)total_txn_count;
    LOG(INFO) << "Current MH txn percentages: NO: " << 100*mh_no/(double)total_txn_count << " P: " << 100*mh_pay/(double)total_txn_count << " OS: " << 100*mh_os/(double)total_txn_count << " D: " << 100*mh_del/(double)total_txn_count << " SL: " << 100*mh_sl/(double)total_txn_count;
  }

  txn->mutable_internal()->set_id(client_txn_id_counter_);
  client_txn_id_counter_++;

  return {txn, pro};
}

void MovrWorkload::GenerateViewVehiclesTxn(Transaction& txn, TransactionProfile&) {
  const std::string city = SampleOnce(rg_, cities_);

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("view_vehicles");
  procedure->add_args(city);  // Only input required in WHERE clause
}

void MovrWorkload::GenerateUserSignupTxn(Transaction& txn, TransactionProfile&) {
  const std::string id = generator::GenerateUUID(rg_);
  const std::string city = SampleOnce(rg_, cities_);
  const std::string name = generator::GenerateName(rg_);
  const std::string address = generator::GenerateAddress(rg_);
  const std::string credit_card = generator::GenerateCreditCard(rg_);

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("user_signup");
  procedure->add_args(id);
  procedure->add_args(name);
  procedure->add_args(address);
  procedure->add_args(city);
  procedure->add_args(credit_card);
}

void MovrWorkload::GenerateAddVehicleTxn(Transaction& txn, TransactionProfile&) {
  std::string id = generator::GenerateUUID(rg_);
  const std::string city = SampleOnce(rg_, cities_);
  const std::string type = generator::GenerateRandomVehicleType(rg_);
  const std::string owner_id = generator::GenerateUUID(rg_); // Link to an already generated user id
  const std::string creation_time = std::to_string(
    std::chrono::system_clock::now().time_since_epoch().count());
  const std::string status = generator::GetVehicleAvailability(rg_);
  const auto loc = generator::GenerateRandomLatLong(rg_);
  const std::string current_location = loc.first + "," + loc.second;
  const std::string ext = generator::GenerateVehicleMetadata(rg_, type);

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("add_vehicle");
  procedure->add_args(id);
  procedure->add_args(city);
  procedure->add_args(type);
  procedure->add_args(owner_id);
  procedure->add_args(creation_time);
  procedure->add_args(status);
  procedure->add_args(current_location);
  procedure->add_args(ext);
}

void MovrWorkload::GenerateStartRideTxn(Transaction& txn, TransactionProfile&) {
  const std::string user_id = generator::GenerateUUID(rg_); // Link to an already generated user
  const std::string vehicle_id = generator::GenerateUUID(rg_); // Link to an already generated vehicle
  const std::string ride_id = generator::GenerateUUID(rg_);
  const std::string city = SampleOnce(rg_, cities_);
  const std::string vehicle_city = SampleOnce(rg_, cities_); // Link to actual vehicle city
  const std::string start_address = generator::GenerateAddress(rg_);
  const std::string start_time = std::to_string(
    std::chrono::system_clock::now().time_since_epoch().count());

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("start_ride");
  procedure->add_args(user_id);
  procedure->add_args(vehicle_id);
  procedure->add_args(ride_id);
  procedure->add_args(city);
  procedure->add_args(vehicle_city);
  procedure->add_args(start_address);
  procedure->add_args(start_time);
}

void MovrWorkload::GenerateUpdateLocationTxn(Transaction& txn, TransactionProfile&) {
  const std::string city = SampleOnce(rg_, cities_);
  std::string ride_id = generator::GenerateUUID(rg_); // Link to an actual ride
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

void MovrWorkload::GenerateEndRideTxn(Transaction& txn, TransactionProfile&) {
  const std::string vehicle_id = generator::GenerateUUID(rg_); // Link to an actual vehicle
  const std::string end_address = generator::GenerateAddress(rg_);
  const std::string end_time = std::to_string(
    std::chrono::system_clock::now().time_since_epoch().count());
  const std::string revenue = generator::GenerateRevenue(rg_);

  auto* procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("end_ride");
  procedure->add_args(vehicle_id);
  procedure->add_args(end_address);
  procedure->add_args(end_time);
  procedure->add_args(revenue);
}

}  // namespace slog