# TDD Cycle Checklist

Strict red-green-refactor rhythm. Follow for every change in the refactoring plan.

## Before starting

- [ ] Run `make test` - confirm GREEN baseline
- [ ] Identify the single thing you are changing this cycle
- [ ] Read the plan step to understand the expected outcome

## For new behaviour (validation, guards, new error paths)

1. **RED** - Write one failing test that specifies the desired behaviour
   - Run `make test` - confirm the new test FAILS and all others PASS
2. **FIX** - Make the minimum code change to pass that test
   - Touch as few lines as possible
   - Do not fix adjacent issues - one thing at a time
3. **GREEN** - Run `make test` - ALL tests must pass
4. **REFACTOR** (optional) - Clean up only if the fix introduced duplication or mess
   - Run `make test` again after any cleanup
5. **COMMIT** - One atomic commit describing what changed and why

## For behaviour-preserving refactors (extract function, remove dead code)

1. **GREEN** - Run `make test` - confirm baseline
2. **REFACTOR** - Make the structural change (extract, rename, delete)
   - The test suite is your safety net - do not change tests and production code in the same step
3. **GREEN** - Run `make test` - all tests must still pass
4. **COMMIT** - One atomic commit

## Rules

- Never batch multiple concerns into one cycle
- If tests break unexpectedly, stop and diagnose before continuing
- If a refactor needs a test that doesn't exist, write the test first (separate commit)
- Run the full suite, not just the file you changed
