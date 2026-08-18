#include <admissionspec/Types.hpp>
#include <rpcspec/JsonBool.hpp>
#include <rpcspec/SpecDumpWriter.hpp>

#include <boost/json/parse.hpp>
#include <boost/json/value_to.hpp>

#include <cstdlib>
#include <iostream>
#include <sstream>

int main()
{
    auto const jsonValue = boost::json::parse(R"({"signer_lists": 1})");
    auto const flag = boost::json::value_to<rpc::spec::JsonBool>(jsonValue.at("signer_lists"));
    if (!flag)
    {
        std::cerr << "JsonBool conversion failed\n";
        return EXIT_FAILURE;
    }

    std::ostringstream out;
    rpc::spec::SpecDumpWriter writer{out};
    writer.header("account_info", [&] { writer.stream() << "  - account\n"; });
    std::cout << out.str();

    auto decision = admission::spec::AdmissionDecision::admit();
    if (decision.dropped())
    {
        std::cerr << "AdmissionDecision dropped\n";
        return EXIT_FAILURE;
    }

    std::cout << "xrpl-spec-spec test_package.cpp completed successfully\n";
    return EXIT_SUCCESS;
}
