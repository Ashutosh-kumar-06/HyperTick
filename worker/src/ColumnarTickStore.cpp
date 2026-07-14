#include "ColumnarTickStore.hpp"

#include <arrow/ipc/reader.h>
#include <algorithm>

#if defined(__GNUC__) || defined(__clang__)
#define SWARM_PREFETCH(addr) __builtin_prefetch((addr), 0, 3)
#elif defined(_MSC_VER)
#include <xmmintrin.h>
#define SWARM_PREFETCH(addr) _mm_prefetch(reinterpret_cast<const char*>(addr), _MM_HINT_T0)
#else
#define SWARM_PREFETCH(addr) ((void)0)
#endif

namespace swarm {

ColumnarTickStore::ColumnarTickStore(const std::string& arrow_path) {
    auto maybe_file = arrow::io::MemoryMappedFile::Open(arrow_path, arrow::io::FileMode::READ);
    if (!maybe_file.ok()) {
        return;
    }
    mmap_file_ = *maybe_file;

    auto maybe_reader = arrow::ipc::RecordBatchFileReader::Open(mmap_file_);
    if (!maybe_reader.ok()) {
        return;
    }
    auto reader = *maybe_reader;

    size_t offset = 0;
    for (int b = 0; b < reader->num_record_batches(); ++b) {
        auto maybe_batch = reader->ReadRecordBatch(b);
        if (!maybe_batch.ok()) {
            continue;
        }
        auto batch = *maybe_batch;

        auto ts = std::static_pointer_cast<arrow::Int64Array>(batch->GetColumnByName("timestamp_ns"));
        auto bid = std::static_pointer_cast<arrow::DoubleArray>(batch->GetColumnByName("bid"));
        auto ask = std::static_pointer_cast<arrow::DoubleArray>(batch->GetColumnByName("ask"));
        auto last = std::static_pointer_cast<arrow::DoubleArray>(batch->GetColumnByName("last"));
        auto vol = std::static_pointer_cast<arrow::Int64Array>(batch->GetColumnByName("volume"));

        if (!ts || !bid || !ask || !last || !vol) {
            continue;
        }

        const size_t rows = static_cast<size_t>(batch->num_rows());
        if (rows == 0) {
            continue;
        }

        batches_.push_back(BatchView{
            ts->raw_values(),
            bid->raw_values(),
            ask->raw_values(),
            last->raw_values(),
            vol->raw_values(),
            rows,
            offset,
        });
        offset += rows;
    }

    size_ = offset;
    valid_ = size_ > 0 && !batches_.empty();
}

bool ColumnarTickStore::locate(size_t index, size_t& batch_idx, size_t& local_idx) const {
    for (size_t b = 0; b < batches_.size(); ++b) {
        const auto& view = batches_[b];
        if (index < view.global_offset + view.rows) {
            batch_idx = b;
            local_idx = index - view.global_offset;
            return true;
        }
    }
    return false;
}

Tick ColumnarTickStore::tick_at(size_t index) const {
    size_t batch_idx = 0;
    size_t local_idx = 0;
    if (!locate(index, batch_idx, local_idx)) {
        return {};
    }
    const auto& v = batches_[batch_idx];
    return Tick{
        v.timestamps[local_idx],
        v.bids[local_idx],
        v.asks[local_idx],
        v.lasts[local_idx],
        v.volumes[local_idx],
    };
}

void ColumnarTickStore::prefetch_batch(size_t start, size_t count) const {
    if (!valid_) {
        return;
    }
    const size_t end = std::min(start + count, size_);
    for (size_t i = start; i < end; i += 64) {
        size_t batch_idx = 0;
        size_t local_idx = 0;
        if (!locate(i, batch_idx, local_idx)) {
            continue;
        }
        const auto& v = batches_[batch_idx];
        SWARM_PREFETCH(v.timestamps + local_idx);
        SWARM_PREFETCH(v.bids + local_idx);
        SWARM_PREFETCH(v.asks + local_idx);
        SWARM_PREFETCH(v.lasts + local_idx);
    }
}

}  // namespace swarm
