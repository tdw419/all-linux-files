# Plan: Repository Initialization and Naming

## Objective
Convert the current project structure into a formal Git repository with a clear name and organized structure.

## Naming Options
The user requested names like "all recent files" or "most recent files". Given the "Linux Everything" inspiration and the core functionality, here are some options:

1. **OmniFile (or Omnifiles)**: Short, professional, implies "everything".
2. **FlashIndex**: Emphasizes the speed of indexing and searching.
3. **LinuxSearch**: Simple and descriptive.
4. **QuickScan**: Focuses on the "fast scan" aspect.
5. **Recent-Everything**: Combines "Recent" with the "Everything" search concept.
6. **Chronofiles**: Focuses on the "recent" (time-based) aspect if that's the primary use case.
7. **L-Everything (or Leverything)**: A nod to its Linux roots and the Windows "Everything" search.

**Recommendation**: **Omnifiles** or **L-Everything**.

## Implementation Steps

### 1. Naming & Repository Initialization
- [ ] Confirm name with user (defaulting to `omnifiles` for this plan).
- [ ] Run `git init`.
- [ ] Create a robust `.gitignore`.

### 2. Project Restructuring (Optional but Recommended)
The current structure has both a Python implementation (`src/`) and a Rust implementation (`linux_everything_rust/`).
- [ ] Consolidate into a single project structure if appropriate, or keep as sub-modules/directories.
- [ ] Rename the root directory (the user will likely do this manually, but the plan should reflect it).

### 3. Documentation Update
- [ ] Create a comprehensive `README.md`.
- [ ] Update internal implementation plans with the new name.

### 4. Verification
- [ ] Verify `git` is initialized correctly.
- [ ] Verify `.gitignore` excludes `target/`, `.venv/`, `.db` files, etc.

## Verification & Testing
- Run `git status` to ensure only desired files are tracked.
- Check if existing search/scan commands still work (should be unaffected by `git init`).
