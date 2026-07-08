## BUILD

Install Rust
```
% curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh && source "$HOME/.cargo/env"
```

Build the wasmi recipe.  There is currently the following options(s);
- coverage=[True, False] Defaults to false, only supported on LLVM
```
% conan create recipes/wasmi/all --version 1.0.9 -s build_type=Debug
# Or with coverage
% conan create recipes/wasmi/all --version 1.0.9 -o "wasmi/*:coverage=True" -s build_type=Debug
```

## Run the test
```
# From the root of this repo
% ./recipes/wasmi/all/test_package/build/<compiler>/test_package 
# or if coverage turned on
% LLVM_PROFILE_FILE=wasmi.profraw ./recipes/wasmi/all/test_package/build/<compiler>/test_package  
% llvm-profdata merge -sparse wasmi.profraw -o wasmi.profdata  
% llvm-cov report ./recipes/wasmi/all/test_package/build/<compiler>/test_package  -instr-profile=wasmi.profdata
```