toc:
	doctoc --notitle --github README.md

# Cut a release: bump version, stamp the changelog, commit and tag.
# Usage: `make bump [patch|minor|major]` (default: patch).
bump:
	./scripts/bump.py $(or $(filter patch minor major,$(MAKECMDGOALS)),patch)

patch minor major:
	@:

.PHONY: toc bump patch minor major
