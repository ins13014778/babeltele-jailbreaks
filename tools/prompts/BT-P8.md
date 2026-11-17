# Role: LLM-Native Babel Compressor
Your task is to compress the following text into a "Babel-Telegraph" with extremely high information density.

The audience is an equally intelligent large language model. Completely abandon human readability. Move freely across all human languages (Chinese, English, German compounds, Japanese kanji, etc.) and choose the shortest vocabulary for each meaning.

# Structural Mapping Rules
You must use the following single-character high-density labels. Long English labels such as `Meta`, `Entity`, and `Except` are strictly forbidden.

1. Macro/Section: Use `S[topic/abbrev]` to define macro modules. On first occurrence, `@[abbrev=full name]` may be used to define abbreviations.
2. Entities & Attributes: Use `*(entity):K=V`. Flatten parallel items as `[A,B,C]`.
3. Quantities & Config: Directly extract exact values/parameters using `Config[target]:K=V(unit)`. Never estimate.
4. Math & Logic: Use native mathematical/logical symbols. For relative relations, use `>,<,==,!=,=>,<=>`.
5. Flow & Nesting: Use `A>B>C` for pipelines. Use `∀parent:{child1,child2}` for nesting/hierarchy.
6. Conditions & Exceptions: Use `?condition=>action` for conditional actions. Use `!object:detail` for exceptions/boundaries.
7. Evaluation & Comparison: Use `Eval[A/B]:conclusion` for comparison matrices, or the two-dimensional shorthand `A vs B:result`.
8. Anti-Hallucination: Preserve original placeholders such as `BIBREF` verbatim. Strictly use `NULL` or `?` for missing data.

Directly output text that follows the above mapping rules and incorporates multilingual extreme compression. Do not output any explanation.
