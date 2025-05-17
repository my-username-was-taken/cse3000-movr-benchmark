#include "execution/movr/constants.h"
#include "execution/movr/transaction.h"
#include "execution/movr/data_generator.h"

namespace slog {
namespace movr {

StartRideTxn::StartRideTxn(const std::shared_ptr<StorageAdapter>& storage_adapter,
  const uint64_t user_id, const std::string& user_city, const std::string& code, const uint64_t vehicle_id,
  const std::string& vehicle_city, const uint64_t ride_id, const std::string& city,
  const std::string& start_address, const int start_time)
    : vehicles_ (storage_adapter),
      rides_ (storage_adapter),
      users_ (storage_adapter),
      user_promo_codes_(storage_adapter) {
  a_user_id_ = MakeInt64Scalar(user_id);
  a_user_city_ = MakeFixedTextScalar<64>(user_city);
  a_code_ = MakeFixedTextScalar<64>(code);
  a_vehicle_id_ = MakeInt64Scalar(vehicle_id);
  a_vehicle_city_ = MakeFixedTextScalar<64>(vehicle_city);
  a_ride_id_ = MakeInt64Scalar(ride_id);
  a_home_city_ = MakeFixedTextScalar<64>(city);
  a_start_address_ = MakeFixedTextScalar<64>(start_address);
  a_start_time_ = MakeInt32Scalar(start_time);
}

bool StartRideTxn::Read() {
  bool ok = true;
  if (auto res = user_promo_codes_.Select({a_user_city_, a_user_id_, a_code_},
    {UserPromoCodesSchema::Column::CODE}); !res.empty()) {
    code_result = UncheckedCast<FixedTextScalar>(res[0]);
  } else {
    SetError("Promo code does not exist");
    ok = false;
  }
  return ok;
}

void StartRideTxn::Compute() {
  
}

bool StartRideTxn::Write() {
  bool ok = true;

  if (!vehicles_.Update({a_vehicle_id_, a_vehicle_city_}, {VehiclesSchema::Column::STATUS},
    {MakeFixedTextScalar<64>(DataGenerator::EnsureFixedLength<64>("in_use"))})) {
    SetError("Cannot update vehicle status");
    ok = false;
  }
  
  if (!rides_.Insert({a_ride_id_, a_home_city_, a_vehicle_city_, a_user_id_, a_vehicle_id_,
    a_start_address_, MakeFixedTextScalar<64>(DataGenerator::EnsureFixedLength<64>("")), a_start_time_, NULL, MakeInt32Scalar(0.0)})) {
    SetError("Cannot insert into rides");
    ok = false;
  }

  return ok;
}

}  // namespace movr
}  // namespace slog