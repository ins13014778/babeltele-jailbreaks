# Compress the following content into the absolute shortest possible token sequence. Do not lose any information. You may refer to the following methods.

1. Macro & Meta: Map text to `Sec:[Name->Content]`. Extract `Meta:[K=V]` and define acronyms via `Def:[Term=FullName]` on first use.
2. Entities & Attributes: Bind via `Ent(Attr=Val)`. Flatten parallel items into arrays `[A, B]`. Retain qualitative examples via `Ex:[a, b, c]`.
3. Quantities & Configs: Isolate exact metrics/hyperparameters via `Quant/Config:[Target->K=Val(Unit)]` without rounding or estimation.
4. Math & Logic: Retain all formulas and variables exactly via `Math:[Eq]`. Use (`>,<,=,->,!=`) for relative or causal relations.
5. Flow & Architecture: Map structural pipelines via `Seq:[A>B>C]` and define nested structures via `Arch:[Main->Sub1, Sub2]`.
6. Conditions & Exceptions: Isolate logic via `if[Cond]->[Act]` and define boundaries/exemptions via `Except:[Target->Detail]`.
7. Evaluations & Comparisons: Extract results to `Eval:[Target->Result]`. Use `Matrix:[Ent(X) vs Ent(Y)]` for multi-condition data and `Ref:[A vs B]` for contrasting systems.
8. Anti-Hallucination: Strictly preserve all original placeholders (e.g., `BIBREF`, `TABREF`). NEVER interpolate missing data; use `@Uncertain` for ambiguous estimates.

Directly output the compressed content.
