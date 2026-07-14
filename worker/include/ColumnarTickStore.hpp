#pragma once

#include "StrategyInterface.hpp"

#include <arrow/api.h>
#include <arrow/io/api.h>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace swarm {

/// Zero-copy Structure-of-Arrays tick store backed by Arrow column buffers.
class ColumnarTickStore {
public:
    static constexpr size_t kDefaultBatchSize = 4096;

    explicit ColumnarTickStore(const std::string& arrow_path);

    bool valid() const { return valid_; }
    size_t size() const { return size_; }

    Tick tick_at(size_t index) const;
    void prefetch_batch(size_t start, size_t count) const;

private:
    struct BatchView {
        const int64_t* timestamps;
        const double* bids;
        const double* asks;
        const double* lasts;
        const int64_t* volumes;
        size_t rows;
        size_t global_offset;
    };

    bool locate(size_t index, size_t& batch_idx, size_t& local_idx) const;

    bool valid_{false};
    size_t size_{0};
    std::vector<BatchView> batches_;
    std::shared_ptr<arrow::io::MemoryMappedFile> mmap_file_;
};

}  // namespace swarm
