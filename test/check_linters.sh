# Testing script only to be called inside the container built by
# `make test`. Ensures that linting succeeds on all well-formed
# test files and fails on all mal-formed ones

failed=0

for file in "/test/lint_tests/should_succeed/*"
do
    /entry $file
    failed=$((failed || $?))
done

for file in "/test/lint_tests/should_fail/*"
do
    ! /entry $file
    failed=$((failed || $?))
done

exit $failed
