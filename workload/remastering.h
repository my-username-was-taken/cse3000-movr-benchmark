#pragma once

#include <vector>

#include "workload/basic.h"

namespace slog {

class RemasteringWorkload : public BasicWorkload {
 public:
  RemasteringWorkload(const ConfigurationPtr& config, RegionId region, ReplicaId replica, const std::string& data_dir,
                      const std::string& params_str, const uint32_t seed = std::random_device()());

  std::pair<Transaction*, TransactionProfile> NextTransaction();
  std::pair<Transaction*, TransactionProfile> NextRemasterTransaction();
};

}  // namespace slog