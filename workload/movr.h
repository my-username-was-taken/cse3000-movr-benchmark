#pragma once

#include <vector>

#include "common/configuration.h"
#include "common/types.h"
#include "execution/tpcc/constants.h"
#include "proto/transaction.pb.h"
#include "workload/workload.h"

using std::vector;

namespace slog {

// Define constants for MovR transaction types
enum class MovrTxnType {
  VIEW_VEHICLES,
  USER_SIGNUP,
  ADD_VEHICLE,
  START_RIDE,
  UPDATE_LOCATION,
  END_RIDE,
  NUM_TXN_TYPES // Keep last
};

class MovrWorkload : public Workload {
 public:
  MovrWorkload(const ConfigurationPtr& config, RegionId region, ReplicaId replica, const std::string& params_str,
               std::pair<int, int> id_slot, const uint32_t seed = std::random_device()());

  std::pair<Transaction*, TransactionProfile> NextTransaction();

 private:
  int local_region() { return config_->num_regions() == 1 ? local_replica_ : local_region_; }

  // Helper methods for generating specific transaction types
  void GenerateViewVehiclesTxn(Transaction& txn, TransactionProfile& pro);
  void GenerateUserSignupTxn(Transaction& txn, TransactionProfile& pro);
  void GenerateAddVehicleTxn(Transaction& txn, TransactionProfile& pro);
  void GenerateStartRideTxn(Transaction& txn, TransactionProfile& pro);
  void GenerateUpdateLocationTxn(Transaction& txn, TransactionProfile& pro);
  void GenerateEndRideTxn(Transaction& txn, TransactionProfile& pro);

  std::vector<int> SelectRemoteWarehouses(int partition);
  int GetRegionFromWarehouse(int warehouse_id);

  ConfigurationPtr config_;
  RegionId local_region_;
  ReplicaId local_replica_;
  std::vector<int> distance_ranking_;
  int zipf_coef_;
  // _warehouse vector has dimensions: partition (currently 2), home/home (2?, i.e., number of 'regions' blocks in the .conf file), and then a list of warehouses that are based there
  vector<vector<vector<int>>> warehouse_index_;
  std::mt19937 rg_;
  TxnId client_txn_id_counter_;
  std::vector<int> txn_mix_;
  std::vector<std::string> cities_;
};

}  // namespace slog