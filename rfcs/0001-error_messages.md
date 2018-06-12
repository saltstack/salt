- Feature Name: Allow packagers to have custom error/suggestion messages
- Start Date: Tue 12 Jun, 2018
- RFC PR:
- Salt Issue:

# Summary
[summary]: #summary

Extract error messages in separate files to allow packagers to customize them

# Motivation
[motivation]: #motivation

Sometimes we need to have custom error/suggestions messages in order to point to the right package names depending on the context (eg: OS)

# Design
[design]: #detailed-design

### Current Design

At the moment, the errors are spread within the code.

### Proposed Design

The simplest solution would be to extract all of them in a separate file.
They could be also be organized by category.
We could also assign unique IDs in order to facilitate documenting them.

### Notes

There might be cases where the messages need to contain some dynamic parts in which case we could store them as string templates and populate them before displaying or find a better solution if needed.

## Alternatives
[alternatives]: #alternatives

Open for suggestions.

## Unresolved questions
[unresolved]: #unresolved-questions

N/A

# Drawbacks
[drawbacks]: #drawbacks


# Trade-offs

