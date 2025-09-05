# How to issue an r2r-ctd release

## Versioning Scheme
r2r-ctd uses [CalVer](https://calver.org/) in the format `YYYY.0M.X` where `X` is the 0 based release number that month.
For example, the first release was `2025.08.0`, had another release occurred that month, it would have been `2025.08.1`.

## Git Tagging
When a commit is tagged, that exact state of the repository becomes the tagged version, so you want the state of the repository to be exactly what you want to be (no placeholder content, tests passing, etc..).

The correct tag for a release is the version string above prefixed with a `v` character.
For the above two examples, the git tags would be `v2025.08.0` and `v2025.08.1`

This tag value is what gets used automatically by the build/publish system for a version number.
Note that the [python machinery](https://packaging.python.org/en/latest/specifications/version-specifiers/#integer-normalization) will drop the leading zeros from the month.

## Steps
1. Do a "prepare" commit to the CHANGELOG.md file that sets the release version and date.
   Take this time to review the items in the changelog for anything that might need fixing or updating.
   Look at [previous](https://github.com/cchdo/r2r-ctd/commit/813ec17b5ce85da1aa88b3e2ca3fdf18b58a91a2) [examples](https://github.com/cchdo/r2r-ctd/commit/78b4cde60fcab55eb0d54e43769179e318b5f8db).
2. Wait for or make sure all the CI tasks are completing: tests, docs building etc.. before continuing.
   Fix anything breaking.
3. Start to draft a new release on the [github releases](https://github.com/cchdo/r2r-ctd/releases) interface.
    a. Click the "Draft new release" button in the upper right.
    b. Set the release tag to the correct value: type it in and pick the "Create new tag" option
    c. The release target should be the master branch
    d. Write a title, should include the version tag value and maybe something clever if you can think of it (have fun)
    e. Make the release notes, try using the "Generate release notes" button and see if that gets everything you need.
       Otherwise include at the minimum the contents of the changelog for this release.
    f. Have the "Set as the latest release" check box checked.
4. Click the green "publish" button.
5. This should trigger a publish GH action that builds and publishes the package to pypi.
   Check to make sure it actually worked.
6. The release version will also be archived to zenodo as a new version.
7. If needed, announce to folks in R2R who are using the software.