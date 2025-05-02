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

// Partition that is used in a single-partition transaction.
// Use a negative number to select a random partition for
// each transaction
constexpr char PARTITION[] = "sp_partition";
// Max number of regions to select warehouse from
constexpr char HOMES[] = "homes";
// Zipf coefficient for selecting regions to access in a txn. Must be non-negative.
// The lower this is, the more uniform the regions are selected
constexpr char MH_ZIPF[] = "mh_zipf";
// Colon-separated list of % of the 5 txn types. Default is: "45:43:4:4:4"
constexpr char TXN_MIX[] = "mix";
// Only send single-home transactions
constexpr char SH_ONLY[] = "sh_only";
// Modify the probability of any item on the new order list coming from a remote warehouse. Default is 0.01.
constexpr char REM_ITEM_PROB[] = "rem_item_prob";
// Modify the probability of any payment txn going to a remote warehouse. Default is 0.01.
constexpr char REM_PAYMENT_PROB[] = "rem_payment_prob";
// Skewness of the workload. A theta value between 0.0 and 1.0. Use -1 for defaul skewing
constexpr char SKEW[] = "skew";

// Should actually contain an equal amount of New Order & Payement. 1 Delivery, 1 Stock Level, 1 Order Status per 10 New Order txns.
// "TPC-C specification requires that 10% of New Order transactions need to access two separate warehouses, which may
// become multi-partition and/or multi-home transactions if those two warehouses are located in separate partitions (which is greater than
// 75% probability in our 4-partition set-up) or have different home regions."
const RawParamMap DEFAULT_PARAMS = {{PARTITION, "-1"}, {HOMES, "2"}, {MH_ZIPF, "0"}, {TXN_MIX, "44:44:4:4:4"},
                                    {SH_ONLY, "0"}, {REM_ITEM_PROB, "0.01"}, {REM_PAYMENT_PROB, "0.01"}, {SKEW, "-1.0"}};
//const RawParamMap DEFAULT_PARAMS = {{PARTITION, "-1"}, {HOMES, "2"}, {MH_ZIPF, "0"}, {TXN_MIX, "45:43:4:4:4"}, {SH_ONLY, "0"}}; // Not sure why they had 45% and 43%?

int new_order_count = 0;
int fsh_no = 0;
int mh_no = 0;

int payment_count = 0;
int fsh_pay = 0;
int mh_pay = 0;

int delivery_count = 0;
int fsh_del = 0;
int mh_del = 0;

int order_status_count = 0;
int fsh_os = 0;
int mh_os = 0;

int stock_level_count = 0;
int fsh_sl = 0;
int mh_sl = 0;

int total_txn_count = 0;

// TODO: Add default params from TPC-C skewness spec
int default_item_skewness = 8191; // maxItems at 100k
int default_cust_skewness = 1023; // maxCust per district at 3k

double org_item_skew = (double) default_item_skewness / tpcc::kMaxItems; // 0.08191
double org_cust_skew = (double) default_cust_skewness / tpcc::kCustPerDist; // 0.341

// Random number generator to 
template <typename G>
int NURand(G& g, int A, int x, int y) {
  std::uniform_int_distribution<> rand1(0, A);
  std::uniform_int_distribution<> rand2(x, y);
  return (rand1(g) | rand2(g)) % (y - x + 1) + x;
}

template <typename T, typename G>
T SampleOnce(G& g, const std::vector<T>& source) {
  CHECK(!source.empty());
  size_t i = std::uniform_int_distribution<size_t>(0, source.size() - 1)(g);
  return source[i];
}

// For the Calvin experiment, there is a single region, so replace the regions by the replicas so that
// we generate the same workload as other experiments
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
    warehouse_index_.push_back(partitions);
  }
  auto num_warehouses = config_->proto_config().tpcc_partitioning().warehouses();
  for (int i = 0; i < num_warehouses; i++) {
    int partition = i % num_partitions;
    int home = i / num_partitions % num_regions;
    warehouse_index_[partition][home].push_back(i + 1);
  }
  id_generator_ = TPCCIdGenerator(num_warehouses, id_slot.first, id_slot.second);

  auto txn_mix_str = Split(params_.GetString(TXN_MIX), ":");
  CHECK_EQ(txn_mix_str.size(), 5) << "There must be exactly 5 values for txn mix";
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
  std::discrete_distribution<> select_tpcc_txn(txn_mix_.begin(), txn_mix_.end());
  switch (select_tpcc_txn(rg_)) {
    case 0:
      NewOrder(*txn, pro, w, partition);
      new_order_count++;
      break;
    case 1:
      Payment(*txn, pro, w, partition);
      payment_count++;
      break;
    case 2:
      OrderStatus(*txn, w);
      order_status_count++;
      break;
    case 3:
      Deliver(*txn, w);
      delivery_count++;
      break;
    case 4:
      StockLevel(*txn, w);
      stock_level_count++;
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

void MovrWorkload::NewOrder(Transaction& txn, TransactionProfile& pro, int w_id, int partition) {
  //LOG(INFO) << "Making new NewOrder txn";
  double skew = params_.GetDouble(SKEW);
  int final_item_skew, final_cust_skew;
  if (skew == -1.0) {
    final_item_skew = org_item_skew;
    final_cust_skew = org_cust_skew;
  } else {
    final_item_skew = skew * tpcc::kMaxItems;
    final_cust_skew = skew * tpcc::kCustPerDist;
  }
  auto txn_adapter = std::make_shared<tpcc::TxnKeyGenStorageAdapter>(txn);
  auto remote_warehouses = SelectRemoteWarehouses(partition);
  int d_id = std::uniform_int_distribution<>(1, tpcc::kDistPerWare)(rg_);
  int c_id = NURand(rg_, final_cust_skew, 1, tpcc::kCustPerDist);
  int o_id = id_generator_.NextOId(w_id, d_id);
  // Partition ID on global scale
  int i_w_id = partition + static_cast<int>(local_region() * config_->num_partitions()) + 1;
  auto datetime = std::chrono::system_clock::now().time_since_epoch().count();
  std::array<tpcc::NewOrderTxn::OrderLine, tpcc::kLinePerOrder> ol;
  std::bernoulli_distribution is_remote(params_.GetDouble(REM_ITEM_PROB));
  std::uniform_int_distribution<> quantity_rnd(1, 10);
  int supply_w_ids[tpcc::kLinePerOrder];
  std::set<int> unique_regions;
  for (size_t i = 0; i < tpcc::kLinePerOrder; i++) {
    auto supply_w_id = w_id;
    if (is_remote(rg_) && !remote_warehouses.empty()) {
      supply_w_id = remote_warehouses[i % remote_warehouses.size()];
      pro.is_multi_home = true;
    }
    ol[i] = tpcc::NewOrderTxn::OrderLine({
        .id = static_cast<int>(i),
        .supply_w_id = supply_w_id,
        .item_id = NURand(rg_, final_item_skew, 1, tpcc::kMaxItems),
        .quantity = quantity_rnd(rg_),
    });
    supply_w_ids[i] = supply_w_id;
    int supply_region = GetRegionFromWarehouse(supply_w_id);
    //LOG(INFO) << "Current Region: " << supply_region;
    unique_regions.insert(supply_region);
  }
  if (pro.is_multi_home) {
    mh_no++;
  }
  // Count number of unique '.supply_w_id's in all Order Lines to get whether we have a FSH or a MH txn
  // Note FSH txns will now be counted both as FSH and MH txns
  //for (int i = 0; i < tpcc::kLinePerOrder; i++) {
  //  LOG(INFO) << "Current SH txn counts: Total: "
  //}
  if (unique_regions.size() == 1 && pro.is_multi_home) {
    pro.is_foreign_single_home = true;
    fsh_no++;
  }

  tpcc::NewOrderTxn new_order_txn(txn_adapter, w_id, d_id, c_id, o_id, datetime, i_w_id, ol);
  new_order_txn.Read();
  new_order_txn.Write();
  txn_adapter->Finialize();

  // Serialize the new Order to a string
  auto procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("new_order");
  procedure->add_args(to_string(w_id));
  procedure->add_args(to_string(d_id));
  procedure->add_args(to_string(c_id));
  procedure->add_args(to_string(o_id));
  procedure->add_args(to_string(datetime));
  procedure->add_args(to_string(i_w_id));
  for (const auto& l : ol) {
    auto order_lines = txn.mutable_code()->add_procedures();
    order_lines->add_args(to_string(l.id));
    order_lines->add_args(to_string(l.supply_w_id));
    order_lines->add_args(to_string(l.item_id));
    order_lines->add_args(to_string(l.quantity));
  }
}

void MovrWorkload::Payment(Transaction& txn, TransactionProfile& pro, int w_id, int partition) {
  double skew = params_.GetDouble(SKEW);
  int final_cust_skew;
  if (skew == -1.0) {
    final_cust_skew = org_cust_skew;
  } else {
    final_cust_skew = skew * tpcc::kCustPerDist;
  }
  auto txn_adapter = std::make_shared<tpcc::TxnKeyGenStorageAdapter>(txn);

  auto remote_warehouses = SelectRemoteWarehouses(partition);
  std::uniform_int_distribution<> d_id_rnd(1, tpcc::kDistPerWare);
  int c_id = NURand(rg_, final_cust_skew, 1, tpcc::kCustPerDist);
  auto datetime = std::chrono::system_clock::now().time_since_epoch().count();
  std::uniform_int_distribution<> quantity_rnd(1, 10);
  std::bernoulli_distribution is_remote(params_.GetDouble(REM_PAYMENT_PROB));

  auto d_id = d_id_rnd(rg_);
  auto c_w_id = w_id;
  auto c_d_id = d_id;
  auto h_id = id_generator_.NextHId(w_id, d_id);
  auto amount = std::uniform_int_distribution<int64_t>(100, 500000)(rg_);
  if (is_remote(rg_) && !remote_warehouses.empty()) {
    c_w_id = SampleOnce(rg_, remote_warehouses);
    c_d_id = d_id_rnd(rg_);
    // Note: all Payment txns that are FSH, are also counted as MH
    pro.is_foreign_single_home = true;
    pro.is_multi_home = true;
    mh_pay++;
    fsh_pay++;
  }
  tpcc::PaymentTxn payment_txn(txn_adapter, w_id, d_id, c_w_id, c_d_id, c_id, amount, datetime, h_id);
  payment_txn.Read();
  payment_txn.Write();
  // Imitating a commit using Finalize()
  txn_adapter->Finialize();

  auto procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("payment");
  procedure->add_args(to_string(w_id));
  procedure->add_args(to_string(d_id));
  procedure->add_args(to_string(c_w_id));
  procedure->add_args(to_string(c_d_id));
  procedure->add_args(to_string(c_id));
  procedure->add_args(to_string(amount));
  procedure->add_args(to_string(datetime));
  procedure->add_args(to_string(h_id));
}

void MovrWorkload::OrderStatus(Transaction& txn, int w_id) {
  auto txn_adapter = std::make_shared<tpcc::TxnKeyGenStorageAdapter>(txn);

  double skew = params_.GetDouble(SKEW);
  int final_cust_skew;
  if (skew == -1.0) {
    final_cust_skew = org_cust_skew;
  } else {
    final_cust_skew = skew * tpcc::kCustPerDist;
  }
  auto d_id = std::uniform_int_distribution<>(1, tpcc::kDistPerWare)(rg_);
  int c_id = NURand(rg_, final_cust_skew, 1, tpcc::kCustPerDist);
  auto max_o_id = id_generator_.max_o_id();
  auto o_id = std::uniform_int_distribution<>(max_o_id - 5, max_o_id)(rg_);

  tpcc::OrderStatusTxn order_status_txn(txn_adapter, w_id, d_id, c_id, o_id);
  order_status_txn.Read();
  txn_adapter->Finialize();

  auto procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("order_status");
  procedure->add_args(to_string(w_id));
  procedure->add_args(to_string(d_id));
  procedure->add_args(to_string(c_id));
  procedure->add_args(to_string(o_id));
}

void MovrWorkload::Deliver(Transaction& txn, int w_id) {
  auto txn_adapter = std::make_shared<tpcc::TxnKeyGenStorageAdapter>(txn);
  double skew = params_.GetDouble(SKEW);
  int final_cust_skew;
  if (skew == -1.0) {
    final_cust_skew = org_cust_skew;
  } else {
    final_cust_skew = skew * tpcc::kCustPerDist;
  }
  int c_id = NURand(rg_, final_cust_skew, 1, tpcc::kCustPerDist);
  auto d_id = std::uniform_int_distribution<>(1, tpcc::kDistPerWare)(rg_);
  auto no_o_id = id_generator_.NextNOOId(w_id, d_id);
  auto datetime = std::chrono::system_clock::now().time_since_epoch().count();
  auto carrier = std::uniform_int_distribution<>(1, 10)(rg_);
  tpcc::DeliverTxn deliver(txn_adapter, w_id, d_id, no_o_id, c_id, carrier, datetime);
  deliver.Read();
  deliver.Write();
  txn_adapter->Finialize();

  auto procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("deliver");
  procedure->add_args(to_string(w_id));
  procedure->add_args(to_string(d_id));
  procedure->add_args(to_string(no_o_id));
  procedure->add_args(to_string(c_id));
  procedure->add_args(to_string(carrier));
  procedure->add_args(to_string(datetime));
}

void MovrWorkload::StockLevel(Transaction& txn, int w_id) {
  auto txn_adapter = std::make_shared<tpcc::TxnKeyGenStorageAdapter>(txn);

  auto d_id = std::uniform_int_distribution<>(1, tpcc::kDistPerWare)(rg_);
  auto o_id = id_generator_.max_o_id();
  std::array<int, tpcc::StockLevelTxn::kTotalItems> i_ids;
  std::uniform_int_distribution<> i_id_rnd(1, tpcc::kMaxItems);
  for (size_t i = 0; i < i_ids.size(); i++) {
    i_ids[i] = i_id_rnd(rg_);
  }
  tpcc::StockLevelTxn stock_level(txn_adapter, w_id, d_id, o_id, i_ids);
  stock_level.Read();
  txn_adapter->Finialize();

  auto procedure = txn.mutable_code()->add_procedures();
  procedure->add_args("stock_level");
  procedure->add_args(to_string(w_id));
  procedure->add_args(to_string(d_id));
  procedure->add_args(to_string(o_id));
  auto items = txn.mutable_code()->add_procedures();
  for (auto i_id : i_ids) {
    items->add_args(to_string(i_id));
  }
}

std::vector<int> MovrWorkload::SelectRemoteWarehouses(int partition) {
  if (params_.GetInt32(SH_ONLY) == 1) {
    return {SampleOnce(rg_, warehouse_index_[partition][local_region()])};
  }

  auto num_regions = GetNumRegions(config_);
  auto max_num_homes = std::min(params_.GetInt32(HOMES), num_regions);
  if (max_num_homes < 2) {
    return {};
  }
  auto num_homes = std::uniform_int_distribution{2, max_num_homes}(rg_);
  auto remote_warehouses = zipf_sample(rg_, zipf_coef_, distance_ranking_, num_homes - 1);

  for (size_t i = 0; i < remote_warehouses.size(); i++) {
    auto r = remote_warehouses[i];
    remote_warehouses[i] = SampleOnce(rg_, warehouse_index_[partition][r]);
  }

  return remote_warehouses;
}

int MovrWorkload::GetRegionFromWarehouse(int warehouse_id) {
  auto num_partitions = config_->num_partitions();
  auto num_regions = config_->num_regions();

  int partition = (warehouse_id - 1) % num_partitions; // Warehouses are 1-indexed
  int region = ((warehouse_id - 1) / num_partitions) % num_regions;

  return region;
}

}  // namespace slog