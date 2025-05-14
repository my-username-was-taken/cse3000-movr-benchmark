#include <random>
#include <string>
#include <utility>
#include <vector>

namespace slog {
namespace movr {

class DataGenerator {
public:
    template <typename T>
    T WeightedChoice(std::mt19937& rng, const std::vector<std::pair<T, double>>& items);

    static std::string GenerateUUID(std::mt19937& rng);
    static std::string GenerateRevenue(std::mt19937& rng);
    static std::string GenerateRandomVehicleType(std::mt19937& rng);
    static std::string GetVehicleAvailability(std::mt19937& rng);
    static std::string GenerateRandomColor(std::mt19937& rng);
    static std::pair<std::string, std::string> GenerateRandomLatLong(std::mt19937& rng);
    static std::string GenerateBikeBrand(std::mt19937& rng);
    static std::string GenerateVehicleMetadata(std::mt19937& rng, const std::string& type);
    static std::string GenerateName(std::mt19937& rng);
    static std::string GenerateAddress(std::mt19937& rng);
    static std::string GenerateCreditCard(std::mt19937& rng);
    static std::string GeneratePromoCode(std::mt19937& rng);
    static std::string GenerateContendedID(std::mt19937& rng, double contention_factor, int max_id);
};

} // namespace movr
} // namespace slog
