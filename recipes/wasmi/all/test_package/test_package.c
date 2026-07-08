#include <wasmi.h>

int main(void) {
    wasm_engine_t *engine = wasm_engine_new();
    if (engine == NULL) {
        return 1;
    }
    wasm_engine_delete(engine);
    return 0;
}
