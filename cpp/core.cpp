#include <pybind11/pybind11.h>
#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

// Exact supported capacity dimensions; never guess a missing unit.
double normalize_capacity(double value, const std::string& unit) {
    if (!std::isfinite(value) || value < 0) throw std::invalid_argument("Capacity must be finite and nonnegative");
    double factor;
    if (unit == "t/year") factor = 1;
    else if (unit == "kt/year") factor = 1000;
    else if (unit == "Mt/year") factor = 1000000;
    else throw std::invalid_argument("Unsupported capacity unit");
    double result = value * factor;
    if (!std::isfinite(result)) throw std::invalid_argument("Capacity overflow");
    return result;
}

// Python passes normalized Unicode code points, avoiding UTF-8 byte distances.
size_t distance(const std::u32string& a, const std::u32string& b) {
    if (a.size() > 256 || b.size() > 256) throw std::invalid_argument("Name exceeds 256 characters");
    std::vector<size_t> row(b.size()+1), next(b.size()+1);
    std::iota(row.begin(), row.end(), 0);
    for (size_t i=0; i<a.size(); ++i) {
        next[0]=i+1;
        for (size_t j=0; j<b.size(); ++j)
            next[j+1]=std::min({row[j+1]+1, next[j]+1, row[j]+(a[i]!=b[j])});
        row.swap(next);
    }
    return row.back();
}
PYBIND11_MODULE(muniquant_core, m) {
    m.doc()="MuniQuant deterministic data-quality kernels";
    m.def("normalize_capacity", &normalize_capacity);
    m.def("name_distance", &distance);
    m.attr("version")="0.1.0";
}
