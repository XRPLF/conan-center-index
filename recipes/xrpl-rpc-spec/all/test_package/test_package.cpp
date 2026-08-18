#include <admissionspec/Types.hpp>
#include <rpcspec/JsonBool.hpp>
#include <rpcspec/SpecDumpWriter.hpp>

#include <boost/json/parse.hpp>
#include <boost/json/value_to.hpp>

#include <cstdlib>
#include <iostream>
#include <sstream>

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
