# Super Productivity Fork Workflow

This project keeps the Home Assistant integration and the SP plugin source. The built-in plugin
and its narrowly scoped local-network exception live in a separate fork of the
official Super Productivity repository. Do not copy the SP source tree into
this repo.

The patch in [`patches/super-productivity-ha-sync.patch`](../patches/super-productivity-ha-sync.patch)
was prepared against official upstream commit `9f44d38952d28d53fda2652afb8f4eb30fb1cc09`
on `master` (2026-11-04). It adds the bundled plugin and permits private/local
requests only when the runtime plugin ID is `sp-ha-sync` and its installed path
is under the trusted bundled-plugins directory. It does not add a general
plugin permission or change the public Plugin API. Other plugins keep the
existing private-network guard. HTTP(S)-only requests, redirect blocking, and
cloud metadata protection remain in place.

## One-time setup

1. On GitHub, create a personal fork of `super-productivity/super-productivity`.
   This is a GitHub UI action; this repository does not create or publish forks.
2. Clone your fork and add the official repository as `upstream`:

   ```bash
   git clone https://github.com/YOUR_GITHUB_NAME/super-productivity.git
   cd super-productivity
   git remote add upstream https://github.com/super-productivity/super-productivity.git
   git fetch upstream
   ```

3. Start the HA branch from the patch's exact base and apply the saved patch:

   ```bash
   git switch -c ha-sync 9f44d38952d28d53fda2652afb8f4eb30fb1cc09
   git apply /path/to/this-repo/patches/super-productivity-ha-sync.patch
   git status --short
   ```

   Replace `/path/to/this-repo` with this repository's local path. Confirm
   the changed files include `packages/plugin-dev/sp-ha-sync/`, the bundled
   plugin registry, and the HTTP request bridge.

4. Commit the patch to your fork:

   ```bash
   git add packages/plugin-dev/scripts/build-all.js packages/plugin-dev/sp-ha-sync src/app/plugins/bundled-plugins.const.ts src/app/plugins/issue-provider/plugin-http.service.ts src/app/plugins/plugin-bridge.service.ts src/app/plugins/plugin-bridge.service.spec.ts
   git commit -m "Add built-in Home Assistant task sync"
   git push -u origin ha-sync
   ```

   After this first commit, Git history is the source of truth. Keep later fixes
   as small commits on `ha-sync`; do not repeatedly apply the original patch.

## When official GitHub updates

Run these commands from your SP clone:

```bash
git fetch upstream
git switch master
git merge --ff-only upstream/master
git push origin master
git switch ha-sync
git rebase master
```

If rebase reports conflicts, resolve them file by file, then run
`git add <resolved-files>` and `git rebase --continue`. To abandon only the
current rebase and return to the pre-rebase branch state, run
`git rebase --abort`. Once the rebase is complete, validate the changes before
updating GitHub:

```bash
npm ci
npm run plugins:build
npx ng test --watch=false --include src/app/plugins/plugin-bridge.service.spec.ts --include src/app/plugins/plugin-security.spec.ts --include src/app/plugins/issue-provider/plugin-http.service.spec.ts
npm run buildFrontend:stage:es6
```

Then update the fork branch with:

```bash
git push --force-with-lease origin ha-sync
git push origin master
```

`--force-with-lease` is needed because rebase rewrites the feature branch. Do
not use plain `--force`. If you have not pushed `master` separately, the second
push is unnecessary.

Build and install a desktop package using the official repository's current
platform-specific packaging instructions. Test the built-in plugin against your
HAOS instance before replacing the installed SP application. Do not assume the
official SP release binary contains your fork's changes.

## Build an RPM

Build on Linux from your `ha-sync` branch. The upstream `electron-builder.yaml`
already defines the RPM target and its post-transaction script; the build below
uses the fork's patched source and does not publish a GitHub release.

```bash
git switch ha-sync
npm ci
npm run buildFrontend:stage:es6
npm run electron:build
npx electron-builder --linux rpm --publish never
```

`buildFrontend:stage:es6` runs the prebuild step, which builds and copies the
built-in plugins before Angular creates the frontend bundle. The RPM should be
under `.tmp/app-builds/`. Check the exact filename before installing:

```bash
find .tmp/app-builds -maxdepth 1 -type f -name '*.rpm' -print
```

On Fedora, install the printed package path with:

```bash
sudo dnf install ./.tmp/app-builds/EXACT_PACKAGE_NAME.rpm
```

The resulting RPM targets the build machine's Linux architecture. For another
architecture, build on that architecture or pass the matching
`--x64`/`--arm64` option if the toolchain supports it. Keep the previous SP
package available until the fork build starts and the HA sync succeeds.

## Updating the saved patch

The saved patch is only the bootstrap for creating the initial feature branch.
After the first commit, update `ha-sync` in the SP fork and commit there. If the
patch must be refreshed for a clean bootstrap, export the feature commits with
`git format-patch` from the SP clone and replace the saved patch deliberately.
Record the new upstream base SHA in this document whenever regenerating it.

## Notes

- Use `upstream/master` as the official baseline; use `origin/master` only as
  your personal mirror of that baseline.
- Review upstream changes touching `plugin-bridge.service.ts`,
  `plugin-http.service.ts`, bundled plugin registration, plugin manifests, or
  plugin tests before rebasing. These are the likely conflict and security
  review points. The local-network exception must remain specific to the
  bundled `sp-ha-sync` ID and runtime path.
- Rebuild after every upstream update. If the targeted tests or frontend build
  fail, do not install that build; resolve the incompatibility first.
- An uploaded copy of this plugin still cannot reach a LAN-only Home Assistant.
  Use the forked desktop build when the Home Assistant address is private.
