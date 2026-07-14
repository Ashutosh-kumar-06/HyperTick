#include "ArrowTickReader.hpp"

#include <arrow/ipc/reader.h>

namespace swarm {

ArrowTickReader::ArrowTickReader(const std::string& arrow_path) {
    auto maybe_file = arrow::io::MemoryMappedFile::Open(arrow_path, arrow::io::FileMode::READ);
    if (!maybe_file.ok()) {
        return;
    }
    auto file = *maybe_file;

    auto maybe_reader = arrow::ipc::RecordBatchFileReader::Open(file);
    if (!maybe_reader.ok()) {
        return;
    }
    auto reader = *maybe_reader;

    for (int i = 0; i < reader->num_record_batches(); ++i) {
        auto maybe_batch = reader->ReadRecordBatch(i);
        if (!maybe_batch.ok()) {
            continue;
        }
        auto batch = *maybe_batch;

        auto ts_col = std::static_pointer_cast<arrow::Int64Array>(batch->GetColumnByName("timestamp_ns"));
        auto bid_col = std::static_pointer_cast<arrow::DoubleArray>(batch->GetColumnByName("bid"));
        auto ask_col = std::static_pointer_cast<arrow::DoubleArray>(batch->GetColumnByName("ask"));
        auto last_col = std::static_pointer_cast<arrow::DoubleArray>(batch->GetColumnByName("last"));
        auto vol_col = std::static_pointer_cast<arrow::Int64Array>(batch->GetColumnByName("volume"));

        if (!ts_col || !bid_col || !ask_col || !last_col || !vol_col) {
            continue;
        }

        const int64_t rows = batch->num_rows();
        ticks_.reserve(ticks_.size() + static_cast<size_t>(rows));

        for (int64_t r = 0; r < rows; ++r) {
            ticks_.push_back(Tick{
                ts_col->Value(r),
                bid_col->Value(r),
                ask_col->Value(r),
                last_col->Value(r),
                vol_col->Value(r),
            });
        }
    }

    valid_ = !ticks_.empty();
}

}  // namespace swarm
