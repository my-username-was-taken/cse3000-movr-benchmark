#pragma once

#include <vector>
#include <string>
#include <random>
#include <chrono> // Required for std::chrono::system_clock
#include <iomanip> // Required for std::fixed, std::setprecision
#include <sstream> // Required for std::stringstream

#include "common/configuration.h"
#include "common/types.h"
#include "proto/transaction.pb.h"
#include "workload/workload.h"

using std::string;
using std::vector;

namespace slog {

// Define constants for MovR transaction types
enum class MovrTxnType {
  VIEW_VEHICLES = 0,
  USER_SIGNUP = 1,
  ADD_VEHICLE = 2,
  START_RIDE = 3,
  UPDATE_LOCATION = 4,
  END_RIDE = 5,
  NUM_TXN_TYPES // Keep last
};

class MovrWorkload : public Workload {
 public:
  MovrWorkload(const ConfigurationPtr& config, RegionId region, ReplicaId replica, const std::string& params_str,
               std::pair<int, int> id_slot, const uint32_t seed = std::random_device()());

  std::pair<Transaction*, TransactionProfile> NextTransaction();

 private:
  // Helper methods for generating specific transaction types
  void GenerateViewVehiclesTxn(Transaction& txn, TransactionProfile& pro, const std::string& city);
  void GenerateUserSignupTxn(Transaction& txn, TransactionProfile& pro, const std::string& city);
  void GenerateAddVehicleTxn(Transaction& txn, TransactionProfile& pro, const std::string& home_city, bool is_multi_home);
  void GenerateStartRideTxn(Transaction& txn, TransactionProfile& pro, const std::string& home_city, bool is_multi_home);
  void GenerateUpdateLocationTxn(Transaction& txn, TransactionProfile& pro, const std::string& city);
  void GenerateEndRideTxn(Transaction& txn, TransactionProfile& pro, const std::string& home_city, bool is_multi_home);

  void InitializeTxnMix();
  void InitializeRegionSelection();
  void LogStatistics();

  // Helper methods for city selection
  std::string SelectHomeCity();
  std::string SelectRemoteCity();

  // Configuration and state
  ConfigurationPtr config_;
  RegionId local_region_;
  ReplicaId local_replica_;
  std::vector<int> distance_ranking_;
  std::mt19937 rg_;

  // Parsed parameters
  int zipf_coef_;
  int multi_home_pct_;
  double contention_factor_;
  bool sh_only_;
  vector<std::string> cities_;
  vector<int> txn_mix_pct_;
  std::discrete_distribution<> select_txn_dist_;
  int num_regions_;
  vector<double> region_request_pct_; // Use double for distribution
  std::discrete_distribution<> select_origin_region_dist_;
  std::bernoulli_distribution multi_home_dist_;
  
  TxnId client_txn_id_counter_;
  std::vector<int> txn_mix_;
};

}  // namespace slog