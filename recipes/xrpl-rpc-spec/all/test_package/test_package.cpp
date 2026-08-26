#include <admissionspec/Types.hpp>
#include <rpcspec/JsonBool.hpp>
#include <rpcspec/SpecDumpWriter.hpp>

#include <cstdlib>
#include <iostream>
#include <sstream>

#if !defined(RPCSPEC_IS_CLIO)
#error "the package's `server` option did not reach the consumer as a define"
#endif

int main() {
    // Verifies rpcspec headers and symbols are present
    rpc::spec::JsonBool flag;
    (void)flag;

    std::ostringstream out;
    rpc::spec::SpecDumpWriter writer{out};
    (void)writer;

    // Verifies admissionspec headers and symbols are present
    auto decision = admission::spec::AdmissionDecision::admit();
    (void)decision;

    std::cout << "xrpl-spec-spec test_package builds successfully\n";
    return 0;
}
