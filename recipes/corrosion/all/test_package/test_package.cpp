#include <cstdint>
#include <iostream>

extern "C" std::uint32_t rust_test_lib_answer();

int main() {
    std::cout << "rust says: " << rust_test_lib_answer() << std::endl;
    return 0;
}
