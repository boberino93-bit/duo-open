# Duo Open Role Template System

Status: canonical project source for Primary, Manager, and Research role prompts.

## Purpose

Duo Open must not rely on hand-copied agent prompts that silently become stale as code and protocols change. The role system is generated from structured project policy and role specifications, then refreshed against the actual changed paths in the repository.

## Canonical inputs

- `.swarm/role_templates/role-specs.json` — shared operating requirements plus full Primary, Manager, and Research missions/responsibilities.
- `.swarm/role_templates/role-impact-map.json` — maps changed project paths to the roles that must reassess them.
- `.swarm/generate_role_templates.py` — deterministic renderer and manifest generator.

Generated outputs under `.swarm/generated/` are build outputs and must not be edited by hand.

## Generation contract

Run:

```bash
python .swarm/generate_role_templates.py --base <base-ref>
```

The generator resolves the current Git revision, derives changed paths, maps them to affected roles, renders a complete role prompt from the shared and role-specific specs, appends role-relevant change context, and writes a checksum/provenance manifest.

The changed-path context is routing evidence, not a substitute for reading the real diff. Every role must inspect relevant code before deciding what changed semantically.

## Automatic synchronization

`.github/workflows/swarm-role-template-sync.yml` runs after changes reach `main`. It regenerates the role prompts and commits changed generated outputs back to `main` with a `[skip ci]` synchronization commit. Pull requests regenerate and fail when the checked-in generated state does not match the canonical spec and PR change range.

This keeps Primary, Manager, and Research templates current as the project changes. It does not replace code review, testing, recovery planning, internal publication, or deployment-package rebuilding.

## Package integration

Changes to role specs, bootstrap routing, AgentBus/Artifactory behavior, schemas, capabilities, repository binding, safety/recovery rules, role workflows, or package/build inputs are package-impact events. Primary owns the release gate; Manager owns coordination and package-state visibility; Research owns evidence quality and implementation-ready findings.

A role package is stale when its generated prompt or required shared protocol differs from the project state it claims to represent. Package builders must consume the generated prompt for the target role and record the generated manifest (or equivalent source revision and hashes) in package metadata. Until an older package builder is wired to do that, the limitation must remain explicit rather than describing that package as synchronized.

## Internal vs GitHub persistence

The live internal Artifactory namespace `/DuoOpen-AgentBus` remains operational coordination authority. GitHub is the durable source/code and recovery mirror. Significant template/protocol releases must be published internally with project/role/provenance metadata and backed up in GitHub; the GitHub SHA must be recorded in the internal release message.

## Release gate

Before declaring a role-template/protocol release complete, verify generated outputs, manifest hashes, affected roles, bootstrap routing, package impact, applicable tests, recovery implications for risky device changes, internal Artifactory publication, and GitHub backup provenance.
