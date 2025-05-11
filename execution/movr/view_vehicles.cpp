#include "execution/movr/constants.h"
#include "execution/movr/transaction.h"

namespace slog {
namespace movr {

ViewVehiclesTxn::ViewVehiclesTxn(const std::shared_ptr<StorageAdapter>& storage_adapter,
  const std::vector<int> ids, const std::string city)
    : vehicles_ (storage_adapter) {

  for (int i = 0; i < ids.size(); i++) {
    a_ids_.push_back(MakeInt32Scalar(ids[i]));
    a_city_ = MakeFixedTextScalar<64>(city);
  }
}

bool ViewVehiclesTxn::Read() {
  bool ok = true;
  for (int i = 0; i < a_ids_.size(); i++) {
    auto res = vehicles_.Select({a_ids_[i], a_city_},
      {VehiclesSchema::Column::ID, VehiclesSchema::Column::CITY, VehiclesSchema::Column::STATUS});

    if (!res.empty()) {
      vehicle_id_results.push_back(UncheckedCast<Int32Scalar>(res[0]));
      city_results.push_back(UncheckedCast<FixedTextScalar>(res[1]));
      city_results.push_back(UncheckedCast<FixedTextScalar>(res[2]));
    } else {
      SetError("Vehicle does not exist");
      ok = false;
    }
  }
  return ok;
}

void ViewVehiclesTxn::Compute() {
  
}

bool ViewVehiclesTxn::Write() {
  return true;
}

}  // namespace movr
}  // namespace slog