#pragma once

#include "StrategyInterface.hpp"

#include <arrow/api.h>
#include <arrow/io/api.h>
#include <memory>
#include <string>
#include <vector>

namespace swarm {

/// REQ-3.1: Zero-copy tick ingestion via Apache Arrow memory-mapped files.
class ArrowTickReader {
public:
    explicit ArrowTickReader(const std::string& arrow_path);

    bool valid() const { return valid_; }
    size_t size() const { return ticks_.size(); }

    /// Sequential iterator — strategies receive ticks only through the event loop.
    const Tick& operator[](size_t index) const { return ticks_[index]; }

private:
    bool valid_{false};
    std::vector<Tick> ticks_;
};

}  // namespace swarm
