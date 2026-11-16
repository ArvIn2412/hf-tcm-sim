# REPRO-01 — Encoder A

Джерело S1, друковані стор.5–6, матриця G та рис.2–3; точний файл v7 відсутній.

\[
G(D)=\begin{bmatrix}1&0&0\\0&D^2+1&D\end{bmatrix}.
\]

Обрана causal convention: input \(u_k=(u_{0,k},u_{1,k})\), state \(s_k=(u_{1,k-1},u_{1,k-2})\), output order (c₂,c₁,c₀):
\[
c₂=u₀,\quad c₁=u₁\oplus u₁[k-2],\quad c₀=u₁[k-1],\quad s_{k+1}=(u₁[k],u₁[k-1]).
\]
За цією convention реалізація алгебраїчно узгоджується з G. Сама G не встановлює serialization, shift direction, state IDs або branch labels; потрібна звірка з exact v7.

|State (prev1,prev2)|Input 00|01|10|11|
|---|---|---|---|---|
|00|000→00|010→10|100→00|110→10|
|10|001→01|011→11|101→01|111→11|
|01|010→00|000→10|110→00|100→10|
|11|011→01|001→11|111→01|101→11|

4 states × 4 input pairs = 16 transitions. Rate 2/3. Initial state (0,0), відсутність tail bits і free final state — project conventions, джерело не встановлює їх повністю. ADR-002 natural-binary triple→8PSK — reconstruction. Δφ=π/4 є приростом; повний phase assignment усіх 16 edges не підтверджено.

Machine-readable файли: REPRO_01_ENCODER_SPEC.json і REPRO_01_ENCODER_TEST_VECTORS.json. Вектори утворені прямою підстановкою рівнянь, незалежно від production encode_step. Властивості: 16 унікальних state/input pairs; один output/destination; F steps дають 2F input та 3F coded bits; жодного прихованого padding.
