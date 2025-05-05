#pragma once

#include <array>

#include "execution/movr/constants.h"
#include "execution/movr/table.h"

namespace slog {
namespace movr {

class MovrTransaction {
 public:
  virtual ~MovrTransaction() = default;
  bool Execute() {
    if (!Read()) {
      return false;
    }
    Compute();
    if (!Write()) {
      return false;
    }
    return true;
  }
  virtual bool Read() = 0;
  virtual void Compute() = 0;
  virtual bool Write() = 0;

  const std::string& error() const { return error_; }

 protected:
  void SetError(const std::string& error) {
    if (error_.empty()) error_ = error;
  }

 private:
  std::string error_;
};

// Specific transaction classes for MovR

class ViewVehiclesTxn : public MovrTransaction {
    public:
     ViewVehiclesTxn(const std::shared_ptr<StorageAdapter>& storage_adapter, const std::string& city, int limit);
     bool Read() final;
     void Compute() final;
     bool Write() final;
   
    private:
     Table<VehiclesSchema> vehicles_;
   
     // Arguments
     FixedTextScalarPtr city_;
     Int32ScalarPtr limit_;
   
     // Read results
     Int32ScalarPtr vehicle_id_result = MakeInt32Scalar();
     FixedTextScalarPtr city_result = MakeFixedTextScalar();
     FixedTextScalarPtr status_result = MakeFixedTextScalar();
};

class UserSignupTxn : public MovrTransaction {
    public:
     UserSignupTxn(const std::shared_ptr<StorageAdapter>& storage_adapter,
        const std::string& user_id, const std::string& city, const std::string& name,
        const std::string& address, const std::string& credit_card);
     bool Read() final;
     void Compute() final;
     bool Write() final;
   
    private:
     Table<UsersSchema> users_;
   
     // Arguments
     Int32ScalarPtr user_id_;
     FixedTextScalarPtr city_;
     FixedTextScalarPtr name_;
     FixedTextScalarPtr address_;
     FixedTextScalarPtr credit_card_;
};

class AddVehicleTxn : public MovrTransaction {
    public:
     AddVehicleTxn(const std::shared_ptr<StorageAdapter>& storage_adapter,
        const std::string& vehicle_id, const std::string& city, const std::string& type,
        const std::string& owner_id, const std::string& owner_city,
        const std::string& creation_time, const std::string& status,
        const std::string& current_location, const std::string& ext);
     bool Read() final;
     void Compute() final;
     bool Write() final;
   
    private:
     Table<VehiclesSchema> vehicles_;
     Table<UsersSchema> users_;
   
     // Arguments
     Int32ScalarPtr vehicle_id_;
     FixedTextScalarPtr home_city_;
     FixedTextScalarPtr type_;
     Int32ScalarPtr owner_id_;
     FixedTextScalarPtr owner_city_;
     Int32ScalarPtr creation_time_;
     FixedTextScalarPtr status_;
     FixedTextScalarPtr current_location_;
     FixedTextScalarPtr ext_;
};

class StartRideTxn : public MovrTransaction {
    public:
     StartRideTxn(const std::shared_ptr<StorageAdapter>& storage_adapter,
        const std::string& user_id, const std::string& user_city, const std::string& vehicle_id,
        const std::string& vehicle_city, const std::string& ride_id, const std::string& city,
        const std::string& start_address, const std::string& start_time);
     bool Read() final;
     void Compute() final;
     bool Write() final;
   
    private:
     Table<VehiclesSchema> vehicles_;
     Table<RidesSchema> rides_;
     Table<UsersSchema> users_;
     Table<UserPromoCodesSchema> user_promo_codes_;
   
     // Arguments
     Int32ScalarPtr user_id_;
     FixedTextScalarPtr user_city_;
     Int32ScalarPtr vehicle_id_;
     FixedTextScalarPtr vehicle_city_;
     Int32ScalarPtr ride_id_;
     FixedTextScalarPtr home_city_;
     FixedTextScalarPtr start_address_;
     Int32ScalarPtr start_time_;
   
     // Read results 
     FixedTextScalarPtr code_result = MakeFixedTextScalar();
};

class UpdateLocationTxn : public MovrTransaction {
    public:
     UpdateLocationTxn(const std::shared_ptr<StorageAdapter>& storage_adapter,
        const std::string& city, const std::string& ride_id, const std::string& timestamp,
        const std::string& lat, const std::string& lon);
     bool Read() final;
     void Compute() final;
     bool Write() final;
   
    private:
     Table<VehicleLocationHistoriesSchema> location_histories_;
   
     // Arguments
     FixedTextScalarPtr city_;
     Int32ScalarPtr ride_id_;
     Int32ScalarPtr timestamp_;
     Int32ScalarPtr lat_;
     Int32ScalarPtr lon_;
   };

   class EndRideTxn : public MovrTransaction {
    public:
     EndRideTxn(const std::shared_ptr<StorageAdapter>& storage_adapter,
        const std::string& ride_id, const std::string& city, const std::string& vehicle_id,
        const std::string& vehicle_city, const std::string& user_city,
        const std::string& end_address, const std::string& end_time, const std::string& revenue);
     bool Read() final;
     void Compute() final;
     bool Write() final;
   
    private:
     Table<VehiclesSchema> vehicles_;
     Table<RidesSchema> rides_;
   
     // Arguments
     Int32ScalarPtr ride_id_;
     FixedTextScalarPtr home_city_;
     Int32ScalarPtr vehicle_id_;
     FixedTextScalarPtr vehicle_city_;
     FixedTextScalarPtr user_city_;
     FixedTextScalarPtr end_address_;
     Int32ScalarPtr end_time_;
     Int32ScalarPtr revenue_;
   };

}  // namespace movr
}  // namespace slog