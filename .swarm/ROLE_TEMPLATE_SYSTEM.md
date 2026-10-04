# Duo Open Role Template System

Status: canonical project source for Primary, Manager, and Research role prompts.

## Purpose

Duo Open must not rely on hand-copied agent prompts that silently become stale as code and protocols change. This system treats role prompts as generated project artifacts. A shared bootstrap core establishes project identity, communication, safety, evidence, recovery, package-sync, and dual-persistence requirements; role overlays add role-specific responsibilities; a change-impact map determines which roles must pay attention to which changed paths.

## Canonical inputs

- `.swarm/role_templates/COMMON.md`
- `.swarm/role_templates/PRIMARY.md`
- `.swarm/role_templates/MANAGER.md`
- `.swarm/role_templates/RESEARCHER.md`
- `.swarm/role_templates/role-impact-map.json`

Generated outputs under `.swarm/generated/` MUST NOT be edited by hand.

## Generation contract

Run:

```bash
python .swarm/generate_role_templates.py --base <base-ref>
```

The generator:

1. resolves the current Git revision;
2. determines changed paths from the supplied base ref (or the previous commit when no base is supplied);
3. maps changed paths to affected roles using `role-impact-map.json`;
4. combines `COMMON.md` with the appropriate role overlay;
5. appends a generated project-change context that names the source revision and role-relevant changed files;
6. writes Primary, Manager, and Research prompts plus a checksum manifest.

The changed-path context is routing evidence, not a semantic substitute for reading the actual diff. Every role must inspect relevant code before acting.

## Automatic synchronization

`.github/workflows/swarm-role-template-sync.yml` runs the generator for changes on `main`. If generated outputs change, the workflow commits those generated outputs back to `main` using a `[skip ci]` commit. Pull requests run generation and fail when committed generated outputs do not match canonical inputs and the PR diff.

This means a project code/protocol change automatically refreshes the role prompts that describe what changed and who owns the follow-up. It does not grant an agent permission to skip review, testing, package rebuilds, or internal Artifactory publication.

## Package integration

Any change to canonical role sources, bootstrap routing, AgentBus, Artifactory behavior, schemas, capabilities, repository binding, safety/recovery rules, manager/research/primary workflows, or package/build logic is an automatic package-impact event. Primary owns the release gate; Manager owns coordination and package-state visibility; Research supplies evidence and implementation-ready findings. A role package is stale when its generated prompt or required shared protocol differs from the project state it claims to represent.

When the existing package builder is invoked, it must consume the generated prompt for the target role and record `.swarm/generated/manifest.json` (or its hashes/source revision) in package metadata. If a package builder cannot do this yet, that limitation is explicit technical debt and the package MUST NOT be described as synchronized.

## Internal vs GitHub persistence

The live internal Artifactory namespace `/DuoOpen-AgentBus` remains the operational coordination authority. GitHub is the durable source/code and recovery mirror. Significant template/protocol releases must be published internally with project/role/provenance metadata and backed up in GitHub. Neither side may silently impersonate the other.

## Release gate

Before declaring a role-template/protocol release complete:

- generated outputs match canonical sources;
- manifest hashes validate;
- affected roles are identified;
- bootstrap points to the current system;
- package impact is assessed for Primary, Manager, and Research;
- applicable tests pass;
- recovery/fail-safe implications are considered before risky device changes;
- internal Artifactory release/message is published;
- GitHub commit SHA is recorded in internal provenance.
