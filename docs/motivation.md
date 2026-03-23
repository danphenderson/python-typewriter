# Motivation

Typewriter was created to address [microsoft/playwright-python#2303](https://github.com/microsoft/playwright-python/issues/2303).

That issue highlighted a recurring inconsistency in Playwright's Python annotations: some places used `Union[T, None]`, others used `Optional[T]`, and some variables or parameters defaulted to `None` without making the optionality explicit in the type annotation.

Typewriter packages that cleanup into a focused codemod so maintainers can standardize a codebase without hand-editing every annotation. The same problem appears outside Playwright too, so the tool is useful anywhere a project wants a consistent `None`-related typing style across a codebase.

Typewriter deliberately keeps the scope small: it solves a specific, repeatable annotation-normalization problem instead of trying to become a general-purpose typing fixer.
