#include <pybind11/pybind11.h>
#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

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
    m.def("name_distance", &distance);
    m.attr("version")="0.1.0";
}
