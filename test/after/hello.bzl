# "load" lint: java_library and java_test are unused and will be removed
load("@rules_java//java:defs.bzl", "java_binary")

def create_binary(name, srcs, deps):
    java_binary(
        name = name,
        srcs = srcs,
        deps = deps,
    )

def extend_sources(srcs, extra):
    # "list-append" lint: srcs += [extra] will become srcs.append(extra)
    srcs.append(extra)
    return srcs
