# REPRO-03 — перевірка затримок і сумування променів

Детермінований kernel реалізує `c_l[n]=h_l[n]x[n-d_l]` з нульовим продовженням поза `[0,N_x)`. Отже `N_out=N_x+max(d_l)`. `source_sample_indices[l,n]=n-d_l` зберігається і для негативних індексів перед початком променя; invalid source indices дають точний нуль внеску. Затримки мають одиницю samples, не symbols/seconds. Fractional delay, rounding і interpolation не підтримуються.

`configs/repro03/two_path_reference_fixture.json` — окремий вручну перевірюваний fixture: три complex input samples, два complex gains, delays 0/2, п'ять очікуваних outputs. Його expected values не викликають production function. Тести додатково перевіряють identity, комплексний gain, pure delay, різні затримки двох променів, boundary tail, індексацію і рівність `received=sum(contributions)+noise`.

Старий `hf_tcm.channels.multipath.apply_multipath` також використовує integer-delay Rician paths, але бере один спільний RNG та має власну нульову ділянку/довжину. REPRO-03 не викликає його: новий runner будує незалежні per-path streams і визначає output alignment окремо. Жоден старий channel module не змінювався.
