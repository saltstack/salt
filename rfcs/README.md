# Salt RFCs

**This document is in a DRAFT status**

Many changes, including bug fixes and documentation improvements can be implemented and reviewed via the normal GitHub pull request workflow.

Some changes though are "substantial", and we ask that these be put through a bit of a design process and produce a consensus among the Salt core team.

The "RFC" (request for comments) process is intended to provide a consistent and controlled path for new features to enter the project.

This process is being **actively developed**, and it will still change as more features are implemented and the community settles on specific approaches to feature development.

## When to follow this process

You should consider using this process if you intend to make "substantial" changes to Salt or its documentation. Some examples that would benefit from an RFC are:

   - A new feature that creates new API surface area
   - The removal of features that already shipped
   - The introduction of new idiomatic usage or conventions

The RFC process is a great opportunity to get more eyeballs on your proposal before it becomes a part of a released version of Salt. Quite often, even proposals that seem "obvious" can be significantly improved once a wider group of interested people have a chance to weigh in.

The RFC process can also be helpful to encourage discussions about a proposed feature as it is being designed, and incorporate important constraints into the design while it's easier to change, before the design has been fully implemented.

Changes that do **NOT** require an RFC:

  - Rephrasing, reorganizing or refactoring
  - Bug fixes
  - Addition or removal of warnings
  - Additions only likely to be _noticed by_ other implementors-of-Salt, invisible to users-of-Salt.

## What the process is

In short, to get a major feature added to Salt, one usually first gets the RFC merged into the repo as a markdown file. At that point the RFC is 'active' and may be implemented with the goal of eventual inclusion into Salt.

## The RFC life-cycle

- Once an RFC becomes active, the feature may be implemented and submitted as a pull request to the Salt repository.
- This still does not mean the feature will be merged, only that the core team has agreed to it in principle.
- The fact that a given RFC has been accepted implies nothing about its implementation priority.
- Modifications to active RFC's can be done in follow-up pull requests.
- We should strive to write each RFC in a way that it will reflect the final design of the feature; However, if during implementation things change, the RFC document should be updated accordingly.

## Implementing an RFC

The author of an RFC is not obligated to implement it. Of course, the RFC author (like any other developer) is welcome to post an implementation for review after the RFC has been accepted.

If you are interested in working on the implementation for an 'active' RFC, but cannot determine if someone else is already working on it, feel free to ask (e.g. by leaving a comment on the associated issue).

## Reviewing RFCs

Each week the team will attempt to review some set of open RFC pull requests.

Every accepted feature should have a core team champion, who will represent the feature and its progress.

**This RFC process owes its inspiration to the [React RFC process], [Yarn RFC process], [Rust RFC process], and [Ember RFC process]**

[React RFC process]: https://github.com/reactjs/rfcs
[Yarn RFC process]: https://github.com/yarnpkg/rfcs
[Rust RFC process]: https://github.com/rust-lang/rfcs
[Ember RFC process]: https://github.com/emberjs/rfcs
