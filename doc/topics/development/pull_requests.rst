.. _pull_requests:

Pull Requests
=============

Salt is a large software project with many developers working together. We
encourage all Salt users to contribute new features, bug fixes and
documentation fixes. For those who haven't contributed to a large software
project before we encourage you to consider the following questions when
preparing a pull request.

This isn't an exhaustive list and these aren't necessarily hard and fast rules,
but these are things we consider when reviewing a pull request.

* Does this change work on all platforms? In cases where it does not, is an
  appropriate and easy-to-understand reason presented to the user? Is it
  documented as-such? Have we thought about all the possible ways this code
  might be used and accounted as best we can for them?

* Will this code work on versions of all Python we support? Will it work on
  future versions?

* Are Python reserved keywords used? Are variables named in a way that will
  make it easy for the next person to understand what's going on?

* Does this code present a security risk in any way? What is the worst possible
  thing that an attacker could do with this code? If dangerous cases are
  possible, is it appropriate to document them? If so, has this been done?
  Would this change pass muster with a professional security audit? Is it
  obvious to a person using this code what the risks are?

* Is it readable? Does it conform to our `style guide`_? Is the code documented
  such that the next person who comes along will be able to read and understand
  it? Most especially, are edge-cases documented to avoid regressions? Will it
  be immediately evident to the next person who comes along why this change was
  made?

.. _`style guide`: https://docs.saltproject.io/en/latest/topics/development/conventions/style.html

* If appropriate, has the person who wrote the code which is being modified
  been notified and included in the process?

* What are the performance implications of this change? Is there a more
  efficient way to structure the logic and if so, does making the change
  balance itself against readability in a sensible way? Do the performance
  characteristics of the code change based on the way it is being invoked
  (i.e., through an API or various command-line tools.) Will it be easy to
  profile this change if it might be a problem?

* Are caveats considered and documented in the change?

* Will the code scale? More critically, will it scale in *both* directions?
  Salt runs in data-centers and on Raspberry Pi installations in the Sahara. It
  needs to work on big servers and tiny devices.

* Is appropriate documentation written both in public-facing docs and in-line?
  How will the user know how to use this? What will they do if it doesn't work
  as expected? Is this something a new user will understand? Can a user know
  all they need to about this functionality by reading the public docs?

* Is this a change in behavior? If so, is it in the appropriate branch? Are
  deprecation warnings necessary? Have those changes been fully documented?
  Have we fully thought through what implications a change in behavior might
  have?

* How has the code been tested? If appropriate are there automated tests which
  cover this? Is it likely to regress? If so, how has the potential of that
  regression been mitigated? What is the plan for ensuring that this code works
  going forward?

* If it's asynchronous code, what is the potential for a race condition?

* Is this code an original work? If it's borrowed from another project or found
  online are the appropriate licensing/attribution considerations handled?

* Is the reason for the change fully explained in the PR? If not for review,
  this is necessary so that somebody in the future can go back and figure out
  why it was necessary.

* Is the intended behavior of the change clear? How will that behavior be known
  to future contributors and to users?

* Does this code handle errors in a reasonable way? Have we gone back through
  the stack as much as possible to make sure that an error cannot be raised
  that we do not account for? Are errors tested for as well as proper
  functionality?

* If the code relies on external libraries, do we properly handle old versions
  of them? Do we require a specific version and if so is this version check
  implemented? Is the library available on the same platforms that module in
  question claims to support? If the code was written and tested against a
  particular library, have we documented that fact?

* Can this code freeze/hang/crash a running daemon? Can it stall a state run?
  Are there infinite loops? Are appropriate timeouts implemented?

* Is the function interface well documented? If argument types can not be
  inferred by introspection, are they documented?

* Are resources such as file-handles cleaned-up after they are used?

* Is it possible that a reference-cycle exists between objects that will leak
  memory?

* Has the code been linted and does it pass all tests?

* Does the change fully address the problem or is it limited to a small surface
  area? By this, I mean that it should be clear that the submitter has looked
  for other cases in the function or module where the given case might also be
  addressed. If additional changes are necessary are they documented in the
  code as a FIXME or the PR and in Github as an issue to be tracked?

* Will the code throw errors/warnings/stacktraces to the console during normal
  operation?

* Has all the debugging been removed?

* Does the code log any sensitive data? Does it show sensitive data in process
  lists? Does it store sensitive data to disk and if so, does it do so in a
  secure manner? Are there potential race conditions in between writing the
  data to disk and setting the appropriate permissions?

* Is it clear from the solution that the problem is well-understood? How can
  somebody who has never seen the problem feel confident that this proposed
  change is the best one?

* What's hard-coded that might not need to be? Are we making sensible decisions
  for the user and allowing them to tune and change things where appropriate?

* Are utility functions used where appropriate? Does this change re-implement
  something we already have code for?

* Is the right thing being fixed? There are cases where it's appropriate to fix
  a test and cases where it's appropriate to fix the code that's under test.
  Which is best for the user? Is this change a shortcut or a solution that will
  be solid in the months and years to come?

* How will this code react to changes elsewhere in the code base? What is it
  coupled to and have we fully thought through how best to present a coherent
  interface to consumers of a given function or method?

* Does this PR try to fix too many bugs/problems at once?

* Should this be split into multiple PRs to make them easier to test and reason
  about?

Pull Request Requirements
=========================

The following outlines what is required before a pull request can be merged into
the salt project. For each of these requirements, an exception can be made
that requires 3 approvals before merge. The exceptions are detailed more below.

All PR requirements
-------------------
  * Approval Required: approval review from core team member OR 1 approval review
    from captain of working group
  * Cannot merge your own PR until 1 reviewer approves from defined list above that
    is not the author.
  * All Tests Pass

Bug Fix PR requirements
-----------------------
  * Test Coverage: regression test written to cover bug fix. Contributors only need
    to write test coverage for their specific changes.
  * Point to the issue the PR is resolving. If there is not an issue one will need
    to be created.

Feature PR requirements
-----------------------
  * Test Coverage: tests written to cover new feature. Contributors only need to write
    test coverage for their specific changes.
  * Release Notes: Add note in release notes of new feature for relative release.
  * Add .. versionadded:: <release> to module's documentation. If you are not certain
    which release your fix will be included in you can include TBD and the PR reviewer
    will let you know the correct name of the release you need to update to the versionadded.

Exceptions to all requirements
------------------------------
As previously stated, all of the above requirements can be bypassed with 3 approvals.
PR's that do not require tests include:

  * documentation
  * cosmetic changes (for example changing from log.debug to log.trace)
  * fixing tests
  * pylint
  * changes outside of the salt directory
