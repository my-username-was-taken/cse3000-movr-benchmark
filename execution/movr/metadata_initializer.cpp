#include "execution/movr/metadata_initializer.h"

#include <glog/logging.h>

namespace slog {
namespace movr {

MovrMetadataInitializer::MovrMetadataInitializer(uint32_t num_regions, uint32_t num_partitions)
    : num_regions_(num_regions), num_partitions_(num_partitions) {}

Metadata MovrMetadataInitializer::Compute(const Key& key) {
  CHECK_GE(key.size(), 4) << "Invalid key";
  uint32_t id = *reinterpret_cast<const uint32_t*>(key.data());
  return Metadata(((id - 1) / num_partitions_) % num_regions_);
}

}  // namespace movr
}  // namespace slog