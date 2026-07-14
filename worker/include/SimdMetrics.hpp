#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <vector>

#if defined(__AVX2__)
#include <immintrin.h>
#define SWARM_HAS_AVX2 1
#endif

namespace swarm {

/// SIMD-accelerated post-loop metric computation (AVX2 when available).
class SimdMetrics {
public:
    static double sum(const double* data, size_t n) {
#ifdef SWARM_HAS_AVX2
        return sum_avx2(data, n);
#else
        double acc = 0.0;
        for (size_t i = 0; i < n; ++i) {
            acc += data[i];
        }
        return acc;
#endif
    }

    static double variance(const double* data, size_t n, double mean) {
#ifdef SWARM_HAS_AVX2
        return variance_avx2(data, n, mean);
#else
        double acc = 0.0;
        for (size_t i = 0; i < n; ++i) {
            const double d = data[i] - mean;
            acc += d * d;
        }
        return n > 1 ? acc / static_cast<double>(n - 1) : 0.0;
#endif
    }

    static double compute_sharpe(const std::vector<double>& returns) {
        if (returns.size() < 2) {
            return 0.0;
        }
        const double mean = sum(returns.data(), returns.size()) / static_cast<double>(returns.size());
        const double var = variance(returns.data(), returns.size(), mean);
        const double stddev = std::sqrt(var);
        if (stddev < 1e-12) {
            return 0.0;
        }
        return (mean / stddev) * std::sqrt(252.0 * 390.0);
    }

    static double compute_max_drawdown(const std::vector<double>& equity) {
        if (equity.empty()) {
            return 0.0;
        }
        double peak = equity.front();
        double max_dd = 0.0;
        for (double e : equity) {
            peak = std::max(peak, e);
            if (peak > 0) {
                max_dd = std::max(max_dd, (peak - e) / peak);
            }
        }
        return max_dd * 100.0;
    }

private:
#ifdef SWARM_HAS_AVX2
    static double sum_avx2(const double* data, size_t n) {
        __m256d acc = _mm256_setzero_pd();
        size_t i = 0;
        for (; i + 4 <= n; i += 4) {
            acc = _mm256_add_pd(acc, _mm256_loadu_pd(data + i));
        }
        alignas(32) double tmp[4];
        _mm256_store_pd(tmp, acc);
        double total = tmp[0] + tmp[1] + tmp[2] + tmp[3];
        for (; i < n; ++i) {
            total += data[i];
        }
        return total;
    }

    static double variance_avx2(const double* data, size_t n, double mean) {
        const __m256d mean_v = _mm256_set1_pd(mean);
        __m256d acc = _mm256_setzero_pd();
        size_t i = 0;
        for (; i + 4 <= n; i += 4) {
            const __m256d d = _mm256_sub_pd(_mm256_loadu_pd(data + i), mean_v);
            acc = _mm256_fmadd_pd(d, d, acc);
        }
        alignas(32) double tmp[4];
        _mm256_store_pd(tmp, acc);
        double total = tmp[0] + tmp[1] + tmp[2] + tmp[3];
        for (; i < n; ++i) {
            const double d = data[i] - mean;
            total += d * d;
        }
        return n > 1 ? total / static_cast<double>(n - 1) : 0.0;
    }
#endif
};

}  // namespace swarm
