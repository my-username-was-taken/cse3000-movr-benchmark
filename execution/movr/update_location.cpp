#include "execution/movr/constants.h"
#include "execution/movr/transaction.h"

namespace slog {
namespace movr {

UpdateLocationTxn::UpdateLocationTxn(const std::shared_ptr<StorageAdapter>& storage_adapter,
  const std::string& city, const int ride_id, const int timestamp,
  const double lat, const double lon)
    : location_histories_ (storage_adapter) {
  a_city_ = MakeFixedTextScalar<64>(city);
  a_ride_id_ = MakeInt32Scalar(ride_id);
  a_timestamp_ = MakeInt32Scalar(timestamp);
  a_lat_ = MakeInt32Scalar(lat);
  a_lon_ = MakeInt32Scalar(lon);
}

bool UpdateLocationTxn::Read() {
  return true;
}

void UpdateLocationTxn::Compute() {
  
}

bool UpdateLocationTxn::Write() {
  bool ok = true;
  
  if (!location_histories_.Insert({a_city_, a_ride_id_, a_timestamp_, a_lat_, a_lon_})) {
    SetError("Cannot insert into Location Histories");
    ok = false;
  }

  return ok;
}

}  // namespace movr
}  // namespace slog