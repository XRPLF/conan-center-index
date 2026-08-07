#include <cstdint>

extern "C" std::uint32_t rust_test_lib_answer();

int main() {
  if (rust_test_lib_answer() == 42) {
    return 0;
  }
  return -1;
}
