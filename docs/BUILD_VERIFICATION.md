# Р¤Р°РєС‚РёС‡РЅР° РїРµСЂРµРІС–СЂРєР° M0

РџРµСЂРµРІС–СЂРµРЅРѕ РїС–Рґ С‡Р°СЃ СЃРєР»Р°РґР°РЅРЅСЏ РїР°РєРµС‚Р° (Linux, Python 3.13.5):

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pip install -e . --no-build-isolation --no-deps` | PASS вЂ” editable package installed locally |
| `python -m pytest -q` | PASS вЂ” **10 passed** |
| `python -m hf_tcm doctor` | PASS вЂ” status M0, next M1 |
| `python -m hf_tcm check-config configs/m0_smoke.json` | PASS вЂ” validated, simulation disabled |
| `hf-tcm doctor` | PASS вЂ” console script works |
| `python -m compileall -q src` | PASS вЂ” Python modules compile |
| `ruff check .`, `ruff format --check .` | NOT RUN вЂ” Ruff was unavailable in this offline build environment |

**РЈРІР°РіР°:** Р·Р°РїСѓСЃРє РІС–РґР±СѓРІСЃСЏ РїС–Рґ Python 3.13.5; РІРёРјРѕРіР° РїСЂРѕ СЃСѓРјС–СЃРЅС–СЃС‚СЊ С–Р·
Python 3.11/3.12 РїРµСЂРµРІС–СЂСЏС”С‚СЊСЃСЏ РѕРєСЂРµРјРѕ РІ CI (С„Р°Р№Р» `.github/workflows/ci.yml`).
РџС–СЃР»СЏ СЂРѕР·РїР°РєСѓРІР°РЅРЅСЏ Сѓ Codex РІРёРєРѕРЅР°Р№ `python -m pip install -e '.[dev]'`,
`python -m pytest -q`, `ruff check .`, `ruff format --check .`.

Р¦Рµ Р»РёС€Рµ M0 (С–РЅС„СЂР°СЃС‚СЂСѓРєС‚СѓСЂР°). РљРѕРґСѓРІР°РЅРЅСЏ, РєР°РЅР°Р»Рё, РґРµРєРѕРґСѓРІР°РЅРЅСЏ,
BER-РµРєСЃРїРµСЂРёРјРµРЅС‚Рё С‰Рµ **РЅРµ СЂРµР°Р»С–Р·РѕРІР°РЅС– С‚Р° РЅРµ РїРµСЂРµРІС–СЂСЏР»РёСЃСЏ**.

## M4.7b вЂ” РїРµСЂРµРІС–СЂРєР° РјРµР¶С– `ChannelTruth` С– pytest tmp_path

РџРѕРїРµСЂРµРґРЅС– 8 РїРѕРјРёР»РѕРє РїРѕРІРЅРѕРіРѕ pytest Р±СѓР»Рё РїРѕРјРёР»РєР°РјРё РїС–РґРіРѕС‚РѕРІРєРё fixtures С–Р·
`tmp_path`, Р° РЅРµ РїР°РґС–РЅРЅСЏРјРё assertion: Windows РїРѕРІРµСЂС‚Р°РІ `PermissionError`
(`WinError 5`) РїС–Рґ С‡Р°СЃ С‡РёС‚Р°РЅРЅСЏ/cleanup pytest temporary root. Р—Р°РїСѓСЃРє С–Р·
`--basetemp` Сѓ workspace СѓСЃСѓРІР°С” Р·Р°Р»РµР¶РЅС–СЃС‚СЊ РІС–Рґ СЃРёСЃС‚РµРјРЅРѕРіРѕ `%TEMP%`; Сѓ
РїРѕС‚РѕС‡РЅРѕРјСѓ sandbox РґРѕСЃС‚СѓРї РґРѕ СЃС‚РІРѕСЂРµРЅРѕС— С‚РёРјС‡Р°СЃРѕРІРѕС— С‚РµРєРё workspace С‚Р°РєРѕР¶ Р±СѓРІ
Р·Р°Р±Р»РѕРєРѕРІР°РЅРёР№, С‚РѕРјСѓ С„С–РЅР°Р»СЊРЅРёР№ РїСЂРѕРіС–РЅ РІРёРєРѕРЅСѓРІР°РІСЃСЏ РїРѕР·Р° sandbox. Р“Р»РѕР±Р°Р»СЊРЅС–
РїСЂР°РІР° РЅРµ Р·РјС–РЅСЋРІР°Р»РёСЃСЏ, Р¶РѕРґРЅС– СЃС‚РѕСЂРѕРЅРЅС– С„Р°Р№Р»Рё РЅРµ РІРёРґР°Р»СЏР»РёСЃСЏ.

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **171 passed in 0.73s**; С„С–РЅР°Р»СЊРЅРёР№ РїСЂРѕРіС–РЅ РїРѕР·Р° sandbox РїС–СЃР»СЏ `PermissionError` РґР»СЏ project-local temp Сѓ sandbox |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 55 files already formatted |

РљР°С‚Р°Р»РѕРі `.pytest-m4-7b-temp/` РІРЅРµСЃРµРЅРѕ РґРѕ `.gitignore`. `-p no:cacheprovider`
РЅРµ Р·РјС–РЅСЋС” РЅР°Р±С–СЂ С‚РµСЃС‚С–РІ; РІС–РЅ РІРёРјРёРєР°С” Р»РёС€Рµ Р·Р°РїРёСЃ pytest cache Сѓ С†СЊРѕРјСѓ Р·Р°РїСѓСЃРєСѓ.

## M5k вЂ” post-confirmatory scientific audit

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | BLOCKED BY EXISTING WINDOWS ACL: 19 setup errors from `PermissionError [WinError 5]` because pytest could not inspect/clean the pre-existing `.pytest-m4-7b-temp` directory. Repeating outside the sandbox produced the same ACL errors. The inaccessible directory was not removed or altered. |
| `python -m pytest -q --basetemp .pytest-m5k-temp -p no:cacheprovider` | PASS вЂ” **728 passed in 4.75s**. Same test suite and cache setting, using a new workspace-local basetemp because the specifically requested path is inaccessible. |
| `ruff check src tests` | PASS вЂ” All checks passed. |
| `ruff format --check src tests` | PASS вЂ” 120 files already formatted. |
| Synthetic M5j print regression, before fix | RED вЂ” 2 failures with the historical `KeyError: 'failure_count'`. |
| Synthetic M5j print regression, after fix | PASS вЂ” 2 passed; completed summary returns success, incomplete run records return failure, and output uses `failure_record_count`. |

M5k's stored-count/bootstrap tests read existing M5j checkpoints and block calls to `_run_one` and `run_adaptive_estimator_diagnostic`; they generated no signal/noise or receiver outputs. The mandated full suite also runs pre-existing deterministic seeded unit/integration fixtures for the M5e/f composition; these are not M5k/M5j evaluation samples and do not touch historical output artifacts. Hash tests confirmed M5f/M5h/M5j outputs unchanged. The historical M5j numerical outputs were not rewritten.

## M4.7c/B0 вЂ” strict configuration profile

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **218 passed in 1.97s**; project-local basetemp, Р·Р°РїСѓСЃРє РїРѕР·Р° sandbox С‡РµСЂРµР· Р№РѕРіРѕ `tmp_path` access restriction |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 57 files already formatted |

Receiver Р»РёС€Р°С”С‚СЊСЃСЏ РІРёРјРєРЅРµРЅРёРј; РєРѕРЅС„С–РіСѓСЂР°С†С–Р№РЅР° РІР°Р»С–РґР°С†С–СЏ РЅРµ РїСЂРёР№РјР°С” ADR С– РЅРµ
РІРёРєРѕРЅСѓС” reconstruction.

## M4.7d/B1 вЂ” С–Р·РѕР»СЊРѕРІР°РЅРёР№ assumed-natural-binary adapter

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **231 passed in 1.15s**; project-local basetemp, Р·Р°РїСѓСЃРє РїРѕР·Р° sandbox РїС–СЃР»СЏ РїРѕРїРµСЂРµРґРЅС–С… Windows `tmp_path` permission failures Сѓ sandbox |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 59 files already formatted |

РўРµСЃС‚РѕРІРёР№ РїСЂРѕРіС–РЅ РІРєР»СЋС‡Р°С” Р°СЂС…С–С‚РµРєС‚СѓСЂРЅРёР№ AST guard РґР»СЏ РІСЃС–С… РјРѕРґСѓР»С–РІ Сѓ `receiver/`; РЅРѕРІРёР№ labeling adapter РЅРµ РјР°С” Р·Р°Р±РѕСЂРѕРЅРµРЅРёС… Р·РІРµСЂРЅРµРЅСЊ РґРѕ `ChannelTruth`. Ruff РїРѕРїРµСЂРµРґР¶РµРЅСЊ РЅРµ РІРёРІС–РІ.

## M4.7e/B2a вЂ” aggregate-I/Q prediction С‚Р° project reconstruction metric

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **257 passed in 1.38s**; project-local basetemp, С„С–РЅР°Р»СЊРЅРёР№ РїСЂРѕРіС–РЅ РїРѕР·Р° sandbox С‡РµСЂРµР· Windows `tmp_path` ACL РѕР±РјРµР¶РµРЅРЅСЏ РІ sandbox |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 61 files already formatted |

РџРѕРІРЅРёР№ suite РІРєР»СЋС‡Р°С” СЃС‚Р°С‚РёС‡РЅРёР№ AST guard: РЅРѕРІРёР№ РјРѕРґСѓР»СЊ Сѓ Р·Р°С…РёС‰РµРЅС–Р№ `receiver/` Р·РѕРЅС– РЅРµ С–РјРїРѕСЂС‚СѓС” Р№ РЅРµ РїСЂРёР№РјР°С” `ChannelTruth`. Ruff РїРѕРїРµСЂРµРґР¶РµРЅСЊ РЅРµ РІРёРІС–РІ.

## M4.7f/B2b-1 вЂ” explicit sample-index alignment

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **284 passed in 1.29s**; project-local basetemp, С„С–РЅР°Р»СЊРЅРёР№ РїСЂРѕРіС–РЅ РїРѕР·Р° sandbox С‡РµСЂРµР· Windows `tmp_path` ACL РѕР±РјРµР¶РµРЅРЅСЏ РІ sandbox |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 63 files already formatted |

РўРµСЃС‚Рё РІРєР»СЋС‡Р°СЋС‚СЊ РґРёРЅР°РјС–С‡РЅРµ СЂРѕР·РјС–С‰РµРЅРЅСЏ РїСЂРѕРјРµРЅС–РІ С–Р· СЏРІРЅРёРјРё delays С‚Р° frame indices С– РєРѕРјРїРѕР·РёС†С–СЋ Р· B2a aggregator-РѕРј. Р—РјС–РЅРµРЅРёР№ production-РєРѕРґ Р»РёС€Р°С”С‚СЊСЃСЏ РІ AST-protected `receiver/`; РЅРѕРІРёС… Р·РІРµСЂРЅРµРЅСЊ РґРѕ `ChannelTruth` РЅРµРјР°С”. Ruff РїРѕРїРµСЂРµРґР¶РµРЅСЊ РЅРµ РІРёРІС–РІ.

## M4.7g/B2b-2 вЂ” isolated project reconstruction forward prediction

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **308 passed in 1.77s**; project-local basetemp |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 65 files already formatted |

РџРѕРІРЅРёР№ suite РІРєР»СЋС‡Р°С” СЂСѓС‡РЅС– integration С‚РµСЃС‚Рё `reconstruction_forward.py`: СѓСЃС– b=0вЂ¦7, РѕРґРёРЅ/РґРІР° synthetic paths, СЏРІРЅС– Р·Р°С‚СЂРёРјРєРё Р№ frame clipping/zero-padding, `project_reconstruction_metric`, permutation invariance, input immutability, РІС–РґСЃСѓС‚РЅС–СЃС‚СЊ `ChannelTruth` Сѓ API С‚Р° source-faithful rejection. РџС–СЃР»СЏ РІРёРїСЂР°РІР»РµРЅРЅСЏ РѕРґРЅРѕРіРѕ import-order lint Р·Р°СѓРІР°Р¶РµРЅСЊ Ruff РЅРµРјР°С”. Receiver С– РґР°Р»С– РЅРµ Р°РєС‚РёРІРѕРІР°РЅРёР№.

## M4.7i/B3b-0 вЂ” explicit-operand reconstruction state-step adapter

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **347 passed in 1.30s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 69 files already formatted |

Р”РѕРґР°РЅРѕ С–Р·РѕР»СЊРѕРІР°РЅРёР№ РѕРґРЅРѕ-РїСЂРѕРјРµРЅРµРІРёР№ РєСЂРѕРє СЃС‚Р°РЅСѓ, С‰Рѕ РїРµСЂРµРґР°С” РІСЃС– operands СЏРІРЅРѕ Р№ РґРµР»РµРіСѓС” СЂРµРєСѓСЂСЃС–СЋ РЅР°СЏРІРЅРѕРјСѓ `paper_recursion.py`. РќРµР·Р°Р»РµР¶РЅС– СЂСѓС‡РЅС– С‚РµСЃС‚Рё РїРµСЂРµРІС–СЂСЏСЋС‚СЊ С„РѕСЂРјСѓР»Сѓ [A](1), РєСЂР°Р№РѕРІС– РїР°СЂР°РјРµС‚СЂРё, РґРІР° РїРµСЂРµС…РѕРґРё, posterior С– С‡Р°СЃРѕРІС– РјС–С‚РєРё. Р РµР·СѓР»СЊС‚Р°С‚ вЂ” explicit-operand reconstruction state-step adapter, **NOT paper-exact estimator**; receiver Р»РёС€Р°С”С‚СЊСЃСЏ РІРёРјРєРЅРµРЅРёРј.

## M4.7j/B3c-0 вЂ” explicit-operand sequential reconstruction estimator

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **355 passed in 0.93s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 71 files already formatted |

РќРѕРІРёР№ runner РїРµСЂРµРґР°С” РєРѕР¶РµРЅ СЏРІРЅРѕ Р·Р°РґР°РЅРёР№ РєСЂРѕРє РґРѕ B3b-0 adapter-Р°; С‚РµСЃС‚Рё РЅРµР·Р°Р»РµР¶РЅРѕ РїРµСЂРµРІС–СЂСЏСЋС‚СЊ СЂСѓС‡РЅС– РґРІРѕ- С– С‚СЂРёРєСЂРѕРєРѕРІС– РѕР±С‡РёСЃР»РµРЅРЅСЏ, Р·РјС–РЅРЅС– operands, clock order, immutable history С‚Р° РїРѕРІС‚РѕСЂРЅС– Р·Р°РїСѓСЃРєРё Р· С‚РѕРіРѕ СЃР°РјРѕРіРѕ initial state. Р¦Рµ **explicit-operand sequential reconstruction estimator, NOT complete paper-exact estimator**; aggregate observation С– forward model РЅРµ РїС–РґРєР»СЋС‡РµРЅС–.

## M4.7k/B3c-1 вЂ” one-path snapshot and integration contract

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **361 passed in 0.79s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 73 files already formatted |

РќРѕРІРёР№ snapshot adapter РїРµСЂРµРІС–СЂСЏС” `L=1`, exact `estimator_time_index`, РєРѕРїС–СЋС” СЃР°РјРµ `full_iq` РІ immutable coefficient array С– РїСЂРѕС…РѕРґРёС‚СЊ AST truth-boundary audit. Р’С–РЅ РЅРµ РїСЂРёР·РЅР°С‡Р°С” sample/symbol/frame correspondence С‚Р° РЅРµ РїС–РґРєР»СЋС‡РµРЅРёР№ РґРѕ forward/pipeline.

## M4.7l/B3c-2 вЂ” controlled M3 baseband / [A](5) compatibility audit

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **364 passed in 0.97s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 74 files already formatted |

Р”РѕРґР°РЅС– synthetic tests Р·С–СЃС‚Р°РІР»СЏСЋС‚СЊ СѓСЃС– `b=0вЂ¦7`, РґРІС– РЅРµРЅСѓР»СЊРѕРІС– РєРѕРЅС‚СЂРѕР»СЊРЅС– coefficient pairs, static single path, no noise С– zero delay; РІРѕРЅРё РїРѕСЂС–РІРЅСЋСЋС‚СЊ M3 complex/IQ, РЅРµР·Р°Р»РµР¶РЅРёР№ [A](5) СЂРѕР·СЂР°С…СѓРЅРѕРє С‚Р° aggregate forward output. РљРѕРЅС‚СЂРѕР»СЊРЅРёР№ РєР°РЅР°Р» oracle РЅРµ С‡РёС‚Р°С” `ChannelOutput.truth`; production-РєРѕРґ С– receiver integration РЅРµ Р·РјС–РЅСЋРІР°Р»РёСЃСЊ.

## M4.7m/B3c-3 вЂ” controlled noiseless L=1 real-channel bridge check

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **368 passed in 1.47s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 75 files already formatted |

РќРѕРІС– РЅРµР·Р°Р»РµР¶РЅС– С‚РµСЃС‚Рё РїС–РґС‚РІРµСЂРґР¶СѓСЋС‚СЊ sample-wise `(-Im,Re)` РґР»СЏ РґРІРѕС… РґС–Р№СЃРЅРёС… `a` С‚Р° РІРѕСЃСЊРјРё С„Р°Р· С–Р· Р·Р±С–РіРѕРј [A](5)/forward; РґРІР° complex `h` РїРѕРєР°Р·СѓСЋС‚СЊ, С‰Рѕ С‚РѕС‚РѕР¶РЅС–СЃС‚СЊ РЅРµ С” Р·Р°РіР°Р»СЊРЅРѕСЋ. Р¦Рµ Р»РёС€Рµ synthetic test convention: production observed-IQ bridge Р»РёС€Р°С”С‚СЊСЃСЏ РЅРµ СЂРµР°Р»С–Р·РѕРІР°РЅРёРј, ADR-012 proposed.

## M4.7n/B3c-4 вЂ” accepted ADR-012 causal one-path explicit-posterior step

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **390 passed in 1.16s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 78 files already formatted |

Р”РѕРґР°РЅРѕ 18 ADR-012 bridge cases С– 4 config-validation cases. Р’РѕРЅРё РїРµСЂРµРІС–СЂСЏСЋС‚СЊ СѓСЃС– 8 С„Р°Р· С– РєРѕРµС„С–С†С–С”РЅС‚Рё `a=0.75,2.0`, СЂС–РІРЅРѕ 8 samples, absolute origins, СЂСѓС‡РЅРµ СЃРµСЂРµРґРЅС” РЅРµРѕРґРЅР°РєРѕРІРёС… samples, РЅРµРїРѕРІРЅРµ/РЅРµРєРѕСЂРµРєС‚РЅРµ РІС–РєРЅРѕ, РїСЂРѕС„С–Р»СЊ/L/delay/NaN/Inf, РЅРµР·Р°Р»РµР¶РЅС– symbol/estimator clock origins, rejection РјР°Р№Р±СѓС‚РЅС–С… prediction/posterior cutoffs, explicit one- С‚Р° two-symbol updates, immutable old state, `full_iq` snapshot С– РІС–РґСЃСѓС‚РЅС–СЃС‚СЊ truth/coefficient arguments. РЈСЃС– РїРѕРїРµСЂРµРґРЅС– 368 tests С‚Р°РєРѕР¶ РїСЂРѕР№С€Р»Рё. РЎС‚Р°РЅ Р·Р°РїСѓСЃРєСѓ: **causal one-path explicit-posterior reconstruction step, NOT complete paper-exact receiver**; `receiver_enabled:false`, `paper_exact:false`.

## M4.7o/B4a вЂ” accepted ADR-003/004/005 and isolated reconstruction posterior adapter

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **417 passed in 1.08s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 80 files already formatted |

Р”РѕРґР°РЅРѕ РЅРµР·Р°Р»РµР¶РЅС– СЂСѓС‡РЅС– РїРµСЂРµС…РѕРґРё, prior, first-observation С‚Р° РґРІРѕРєСЂРѕРєРѕРІС– posterior oracles; permutation check С‚Р° РїРµСЂРµРІС–СЂРєРё large-value/log-shift С– overflow inputs. РџРѕС‚РѕС‡РЅР° СЃС‚СЂСѓРєС‚СѓСЂРЅР° РјР°СЃРєР° РјР°С” 16 edges С– С„Р°РєС‚РёС‡РЅРёР№ degree `d(h)=4` Сѓ РєРѕР¶РЅРѕРјСѓ СЂСЏРґРєСѓ, Р°Р»Рµ builder РѕР±С‡РёСЃР»СЋС” `d(h)` Р·Р°РјС–СЃС‚СЊ hardcode. Initial prior РґР°С” `1/4` Р»РёС€Рµ РґР»СЏ С‡РѕС‚РёСЂСЊРѕС… `current_state=(0,0)` edges. РџРµСЂС€Рµ observation РѕРЅРѕРІР»СЋС” С†РµР№ prior Р±РµР· transition; РЅР°СЃС‚СѓРїРЅС– РєСЂРѕРєРё РґРµР»РµРіСѓСЋС‚СЊ transition-plus-emission РґРѕ `coding.posterior.posterior_update()`.

ADR-003/004/005 РїСЂРёР№РЅСЏС‚С– Р»РёС€Рµ СЏРє project policies; SCI-02/SCI-03/SCI-METRIC-02 РІС–РґРєСЂРёС‚С–. `F_rx` вЂ” aggregate reconstruction metric, РЅРµ `paper_metric.py`/[A](2); `beta` СЏРІРЅРёР№ С– Р±РµР· noise variance. РЎС‚Р°С‚СѓСЃ: **isolated reconstruction posterior adapter, NOT author-exact posterior, NOT integrated adaptive receiver**. B4b integration Р»РёС€Р°С”С‚СЊСЃСЏ BLOCKED РґРѕ СЏРІРЅРѕРіРѕ candidate-metric ordering, symbol/edge clock mapping С– cutoff provenance. M1вЂ“M4 regression suite РїСЂРѕР№С€Р»Р°; `paper_exact:false`, `receiver_enabled:false`.

## M4.7p/B4b ? isolated causal reconstruction candidate metrics

Added `generate_reconstruction_candidate_metrics()` for one target symbol and all 16 canonical edge hypotheses. It derives candidate phase from each M1 `output_bits` triple through the existing assumed-natural-binary labeling, uses only the pre-observation state's `full_iq`, calls the existing one-symbol forward model, extracts eight ADR-012 per-sample observations, and delegates residual summation to `compute_project_reconstruction_metric()`. The immutable `(16,)` vector and row metadata carry hypothesis order, output bits, phase indices, sample/symbol/estimator labels and profile provenance. No posterior or estimator update is called.

Independent tests cover all 16 hypotheses and all eight phase labels, noiseless real-channel oracles at amplitudes 0.75 and 2.0, M1 output agreement, per-sample manual metrics, repeated output-bit rows, permutation consistency, nonzero absolute origins, incomplete/non-finite buffers, unsupported profiles, clock labels, input immutability and the distinction between sum of sample residuals and residual of the mean. The result is **isolated causal reconstruction candidate-metric generator, NOT paper-exact metric, NOT autonomous adaptive receiver**. B4a can consume the ordered vector as an emission operand; full information-bit decoding still needs path search/traceback and termination rules. `paper_exact:false`, `receiver_enabled:false`; SCI-METRIC-02 remains open.

Verification for M4.7p/B4b: `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` ? **436 passed**; `ruff check src tests` ? **All checks passed**; `ruff format --check src tests` ? **82 files already formatted**. The sandboxed pytest attempt was blocked during Windows cleanup of the project-local basetemp; the same required command passed when rerun with elevated filesystem access.

## M4.7q/B4c ? isolated causal posterior-estimator step

Added one-symbol composition from B4b candidate metrics to B4a current posterior and the existing causal state step. The API requires explicit first-edge/later-edge mode, exactly one corresponding prior operand, `beta`, estimator parameters, state and clock labels, profile, received labels and exact causal cutoffs. It freezes the pre-state snapshot, validates canonical hypothesis/output-bit/phase ordering, creates `(16,2)` [A](5) recursion predictions, and checks them against B4b's immutable `(16,8,2)` predictions. The causal adapter then extracts the ADR-012 mean-of-eight observation, delegates the state update, and returns a next-symbol-only snapshot.

Independent tests cover a hand-calculated first-edge posterior without transition, hand-calculated later-edge transition/emission, manual [A](1) coefficient updates, two consecutive symbols, beta sensitivity, alpha 0/1, zero gain and zero/nonzero innovations, nonzero origins, future-buffer isolation, old-state/received immutability, prediction consistency, order/clock/cutoff/window/finite-input rejection and the existing ChannelTruth AST boundary. Status: **isolated causal single-path reconstruction posterior-estimator step, NOT paper-exact receiver, NOT decoded-bit output**. B4c one-step gate is READY; autonomous sequence and B5/B6 remain out of scope.

Verification for M4.7q/B4c: `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` ? **451 passed**; `ruff check src tests` ? **All checks passed**; `ruff format --check src tests` ? **84 files already formatted**.

## M4.7r/B4d ? isolated causal single-path sequence runner

Added the B4d scheduler as a caller of the existing B4c step. It validates an exact contiguous `8N` sample buffer and absolute labels, explicit consecutive symbol schedule, the independent `(symbol_index, estimator_time_index)` mapping, and either new-sequence ADR-004 initialization or continuation predecessor posterior/state/clocks. It uses one initial edge update without transition, then transitions once per later symbol, passing each returned posterior and state forward. Recursive parameters accept explicit constants or complete per-symbol schedules. Per-symbol history is optional and immutable.

Tests compare two- and three-symbol sequence runs with a manual chain of B4c calls; verify first/later edge modes, posterior normalization/order, state handoff, changing `mu0`, beta sensitivity, nonzero origin, invalid clocks/symbol schedules/windows/inputs, no future-sample influence, deterministic restart and split-run continuation equivalence. The runner is **isolated causal single-path reconstruction posterior-estimator sequence runner, NOT paper-exact receiver, NOT decoded-bit output**. It does not reset at frame boundaries or connect CLI/pipeline.

Verification for M4.7r/B4d: `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` ? **468 passed**; `ruff check src tests` ? **All checks passed**; `ruff format --check src tests` ? **86 files already formatted**.

## M5a вЂ” reconstruction BER/SER evaluation contract

Added `src/hf_tcm/evaluation/error_metrics.py` and
`tests/test_evaluation_error_metrics.py`. Utilities strictly count information
bit mismatches and coded-symbol index mismatches, map reference M1 output bits
and decoded edge output bits through explicit ADR-002 labeling, validate exact
`2F`/`F` lengths and value ranges, and pool raw counts before calculating
ratios. Tests cover zero/all/partial errors, F=1/2/4/6, independent bit versus
symbol errors, invalid shapes/lengths/values, unequal run lengths, immutable
inputs, deterministic results, mapping coverage, and the no-truth boundary.

No channel/noise generator or M1вЂ“M4 receiver behavior changed; no Monte Carlo,
SNR sweep, baseline comparison, confidence interval, or performance claim was
run. M2 matched-baseline and SNR gates remain BLOCKED. Draft ADR-014 is proposed
for future cluster-bootstrap uncertainty intervals only; it is not accepted.
`paper_exact:false`, `receiver_enabled:false`, accepted ADR-001/002/003/004/005/
006/007/008/010/012/013, proposed ADR-009/011/014, and SCI-02/SCI-03/
SCI-METRIC-02 open are preserved.

Verification for M5a: `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` вЂ” **562 passed in 1.65s**; `ruff check src tests` вЂ” **All checks passed**; `ruff format --check src tests` вЂ” **97 files already formatted**. The focused evaluation test run reported **23 passed**.

## M5b вЂ” reproducible received-to-bits smoke experiment

Added `evaluation/reconstruction_smoke_experiment.py` and
`tests/test_reconstruction_smoke_experiment.py`. The evaluation-side harness
requires a run ID, F, reference bits, real gain, exact complex perturbation and
provenance, sample/symbol/estimator origins, a configuration accepted by the
existing inactive-profile validator, initial CSI provenance, receiver mode,
and a complete explicit partition for segmented mode. It creates M1/ADR-002
symbols, calls the M3 rectangular-ZOH waveform helper, applies explicit real
gain and perturbation, calls B5c or B5d, and only then evaluates reference bits
and coded-symbol indices. Tests verify that reference bits and gain are not
receiver call operands, and no ChannelTruth dependency was introduced.

Noiseless controls passed for gains 0.75 and 2.0 and F=1,2,4,6, using explicit
oracle-initialized fixed estimates; all returned zero bit/symbol errors and
valid paths. Three one-sample deterministic perturbations and a larger explicit
perturbation were evaluated without assigning any noise distribution or SNR.
B5c and B5d results matched for the same F=6 received buffer and partition
`(1,2,3)`. Unequal-length pooled raw counts matched the manual result and
retained both run records. No SNR sweep, Monte Carlo batch, M2 comparison,
confidence interval, or performance claim was run. ADR-014 remains proposed;
`paper_exact:false`, `receiver_enabled:false`, SCI-METRIC-02 open.

Verification for M5b: `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` вЂ” **584 passed in 2.06s**; `ruff check src tests` вЂ” **All checks passed**; `ruff format --check src tests` вЂ” **99 files already formatted**. The focused smoke test run reported **22 passed**.

## M4.7v/B5d вЂ” segmented single-path reconstruction decode

Added `receiver/reconstruction_segmented_decode.py` and
`tests/test_reconstruction_segmented_decode.py`. The adapter validates an
explicit segment partition over one complete received buffer, runs B4d once in
independent mode and then in continuation mode for later segments, copies exact
metric/posterior rows from immutable history, and invokes B5b once after all
segments. Results retain `(F,16)` frozen costs and posterior history, final
states, decoded bits/path, absolute clocks/cutoffs, segment buffer boundaries,
segment-local positions, and independent-sequence positions.

Tests compare monolithic and segmented results for F=1,2,4,6; all requested
partitions; noiseless real-channel oracle coefficients 0.75 and 2.0; and varying
explicit per-symbol recursion schedules. They also cover exact continuation
handoff, one B5b call, invalid/gapped/overlapping/duplicate layouts, incomplete
windows and sample labels, nonzero origin, separate estimator clock,
immutability/determinism, and the no-truth AST boundary. This confirms
deterministic B4d continuation equivalence only; it does not integrate the
frame-constant forward convention or add BER/SER evaluation.

Verification for M4.7v/B5d: `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` вЂ” **539 passed in 1.61s**; `ruff check src tests` вЂ” **All checks passed**; `ruff format --check src tests` вЂ” **94 files already formatted**.

## M4.7u/B5c вЂ” isolated end-to-end single-path composition

Added `receiver/reconstruction_conditional_decode.py`, which runs B4d for one
explicit independent sequence, copies each exact B4c metric row from B4d's
immutable history into a canonical read-only `(F,16)` matrix, and invokes B5b
once. It returns the B5b decoded bits/path and cost, final estimator state and
posterior, frozen metrics, and per-symbol timing/profile provenance. No row is
recomputed using the final estimator state. Added
`tests/test_reconstruction_conditional_decode.py` for manual B4d+B5b composition,
noiseless oracle decoding with real coefficients 0.75 and 2.0 for F=1,2,4,
beta-dependent posterior/state handoff, timing and input rejection,
immutability/determinism, no-truth boundary, and B4d split continuation row
equivalence followed by one B5b call.

The wrapper accepts only a complete independent sequence beginning at the
explicit trellis origin `(0,0)`. It does not support fragment stitching itself;
B4d continuation can be run explicitly, its exact metric rows joined by a
caller, then decoded in one B5b call. Reporting frame boundaries do not reset
the estimator or trellis. Frame scheduling, frame-constant forward-model
compatibility, general complex fading/multipath, and statistical BER/SER remain
outside this integration. No ADR was added; ADR-009/011 remain proposed,
ADR-013 remains accepted, `paper_exact:false`, `receiver_enabled:false`, and
SCI-02/SCI-03/SCI-METRIC-02 remain open.

Verification for M4.7u/B5c: `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` вЂ” **519 passed in 1.20s**; `ruff check src tests` вЂ” **All checks passed**; `ruff format --check src tests` вЂ” **92 files already formatted**.

## M4.7s/B5a вЂ” TCM trajectory/path contract and decoder readiness

Added `M4_B5_TRELLIS_PATH_CONTRACT.md` and the isolated `coding.hypothesis_path.validate_hypothesis_edge_path()` validator. It validates only an explicit caller-supplied edge sequence against the M1 initial state and adjacency. No Viterbi, beam search, traceback, or decoded-bit output was added. Contract tests verify all 16 hypotheses against M1 `build_trellis()`/`encode_step()`, canonical ordering, structural adjacency versus B4a's transition matrix, valid/invalid paths, two input bits per edge, edge IDs distinct from phase labels, one hand-summed conditional path cost, and explicit absolute/frame-local symbol/sample labels.

The narrow path profile remains `reconstructed_offline`, L=1, real-channel experiment, zero delay, rectangular ZOH, 8 samples/symbol. B4b metrics are eligible only for the proposed conditional frozen-cost objective; B4a posterior is not an additive branch metric, and neither is [A](2). ADR-013 is proposed only. Initial state is `(0,0)` for an independent sequence; reconstruction final-state/termination and tie policy remain undecided. `U0`/`U**` and the frame-constant forward schedule remain blocked. No ADR status was otherwise changed; SCI-METRIC-02 remains open, `paper_exact:false`, `receiver_enabled:false`.

Verification for M4.7s/B5a: `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` вЂ” **479 passed in 1.11s**; `ruff check src tests` вЂ” **All checks passed**; `ruff format --check src tests` вЂ” **88 files already formatted**.

## M4.7t/B5b вЂ” accepted ADR-013 conditional reconstruction Viterbi

ADR-013 was accepted by explicit user decision on 2026-10-28. Added the isolated `decode_reconstruction_viterbi()` over caller-supplied frozen B4b costs `(F,16)` in canonical `HYPOTHESES` order. It performs full four-state dynamic programming from `(0,0)`, allows any reachable final state, adds no tails, uses exact tie comparisons (minimum hypothesis ID for tied survivors and minimum M1 state index for tied final costs), then validates full traceback and returns `(F,2)` input pairs and `(2F,)` decoded information bits. Edge, absolute-symbol, and estimator-time labels remain separate and explicit. Continuation is rejected. No B4d orchestration, frame scheduler, CLI, beam search, paper metric, receiver activation, or truth input was added.

Independent tests compare F=1..4 cases against a brute-force enumeration of all allowed paths; check the globally constrained path when row-wise argmins are incompatible; verify tie rules, input/output shapes, free final state, unreachable states, overflow rejection, label continuity, frame-reporting continuity, no-truth AST boundary, immutability, and determinism. The result is **isolated conditional reconstruction Viterbi decoder, NOT paper-exact joint receiver, NOT integrated adaptive receiver**. ADR-009/011 remain proposed; ADR-013 accepted. SCI-02, SCI-03 and SCI-METRIC-02 remain open; `paper_exact:false`, `receiver_enabled:false`.

Verification for M4.7t/B5b: `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` вЂ” **505 passed in 1.30s**; `ruff check src tests` вЂ” **All checks passed**; `ruff format --check src tests` вЂ” **90 files already formatted**.

Verification for M4.7r/B4d: `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` ? **468 passed**; `ruff check src tests` ? **All checks passed**; `ruff format --check src tests` ? **86 files already formatted**.

## M5c вЂ” sample-energy/noise calibration audit

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **598 passed in 1.84s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 101 files already formatted |

РќРѕРІС– 14 РґС–Р°РіРЅРѕСЃС‚РёС‡РЅРёС… С‚РµСЃС‚С–РІ РїРµСЂРµРІС–СЂСЏСЋС‚СЊ unit-magnitude РІРѕСЃСЊРјРёС„Р°Р·РЅСѓ 8PSK,
`a=0.75/2.0`, С‚РѕС‡РЅС– ZOH sample sums, symbol-rate С– sample-sum СЂРѕР·СЂС–Р·РЅРµРЅРЅСЏ,
РґРµС‚РµСЂРјС–РЅРѕРІР°РЅС– I/Q powers, covariance-based variance СЃРµСЂРµРґРЅСЊРѕРіРѕ, invalid
operands С– РІС–РґСЃСѓС‚РЅС–СЃС‚СЊ ChannelTruth Сѓ РјРѕРґСѓР»С–. Р–РѕРґРµРЅ stochastic channel,
SNR sweep, Monte Carlo, matched baseline С‡Рё confidence interval РЅРµ Р·Р°РїСѓСЃРєР°РІСЃСЏ.
ADR-015 РЅР° РµС‚Р°РїС– M5c Р±СѓР»Р° proposed; Сѓ M5d РєРѕСЂРёСЃС‚СѓРІР°С‡ СЏРІРЅРѕ РїСЂРёР№РЅСЏРІ РІСѓР·СЊРєРёР№
РґРёСЃРєСЂРµС‚РЅРёР№ РїСЂРѕС„С–Р»СЊ. Р†РЅС€С– ADR С‚Р° РїРёС‚Р°РЅРЅСЏ SCI РЅРµ Р·РјС–РЅРµРЅРѕ.
`paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02
Р·Р°Р»РёС€Р°СЋС‚СЊСЃСЏ Р±РµР· Р·РјС–РЅ.

## M5d вЂ” paired discrete-AWGN M2/B5 control

Added `evaluation/matched_m2_observation.py` and
`evaluation/matched_m2_b5_experiment.py`, plus focused tests. The M2 adapter
uses exactly the mean of each eight-sample window divided once by explicit
oracle real gain `a`. The harness creates one immutable received buffer from
the M1/M3 control waveform and either one explicit noise array or one explicit
PCG64 noise stream; M2 and B5 reuse that buffer. B5 runs with oracle-initialized
`(a,a)` estimates and frozen explicit recursion settings. Result records retain
the sample hash and time/provenance metadata but no reference arrays in the
receiver outputs.

Accepted ADR-015 defines `gamma_b_eff=4aВІ/sigma_squared` as an effective
discrete label only. The M2/B5 branch identity is
`F_B5=8aВІ*F_M2 + sum_k|received-mean(received)|ВІ`; it was checked numerically
for the tested controls. No physical Eb/N0, performance, sweep, Monte Carlo,
confidence interval, or paper reproduction claim is made. ADR-014 remains
proposed; `paper_exact:false` and `receiver_enabled:false` remain unchanged.

| РљРѕРјР°РЅРґР° | Р¤Р°РєС‚РёС‡РЅРёР№ СЂРµР·СѓР»СЊС‚Р°С‚ |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **628 passed in 1.98s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 105 files already formatted |

New M5d tests cover exact sample-window labels, mean-of-eight and `/a`, gamma
conversion, validation, zero-noise controls for `F=1,2,4` and `a=0.75,2.0`,
explicit deterministic perturbations, seeded PCG64 reproducibility, shared
received provenance, M2/B5 metric identity, unique paths, tie behavior,
reference-data boundary, and no-ChannelTruth imports. Three short seeded runs
and three literal perturbation controls are recorded in
`M5_MATCHED_M2_B5_EXPERIMENT_REPORT.md`; they are smoke controls only.

## M5e вЂ” adaptive estimator diagnostics

Added the isolated evaluation composition in
`evaluation/reconstruction_adaptive_diagnostics.py` and
`tests/test_reconstruction_adaptive_diagnostics.py`. It runs oracle-frozen,
mismatched-frozen, and mismatched-adaptive B4d passes on the exact same
immutable received buffer, captures actual per-symbol B4d history, and invokes
B5b once per mode. Hand calculation of the first [A](1) update, causality,
state immutability/decomposition, two mismatched initial estimates, two
explicit adaptive parameter profiles, seeded ADR-015 repeatability, and
monolithic/segmented equivalence are covered. A deterministic fixture includes
a case where adaptive decoding has more errors than frozen decoding; this is
not treated as a performance estimate.

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **648 passed in 3.70s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 107 files already formatted |

No M1-M3 or B4/B5 mathematical kernels, `paper_metric.py`,
`reconstruction_forward.py`, ADR status, `paper_exact:false`, or
`receiver_enabled:false` were changed. ADR-014 remains proposed; no Monte
Carlo, SNR sweep, confidence interval, matched adaptive-CSI comparison, or
performance claim was produced.

## M5f вЂ” paired cluster-bootstrap experiment

Implemented the ADR-014 cluster-bootstrap utility, explicit paired-Monte-Carlo
configuration/runner, 12-run preset, raw run-record artifact, and tests. The
experiment uses the existing M5e B4d/B5b composition; no receiver or
mathematical kernel was rewritten. The checked-in 12-by-32 run generated one
ADR-015 noise realization per run, shared it between B and C, then ran 2000
paired cluster-bootstrap resamples with seed `2026102803`. The observed study
emitted small/rare/degenerate/unreliable warnings and is not a validated
performance comparison.

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **677 passed in 3.78s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 111 files already formatted |

Focused new M5f tests: **29 passed in 0.83s**. They cover manual paired
resample calculations, unequal-length pooled ratios, same-index B/C sampling,
known and zero-error cases, exact seed replay, invalid counts/configuration,
shared received hashes, state parity/frozen invariance, B4d truth/reference
boundary, and the checked-in validated preset.

ADR-014 is accepted; ADR-009/011 remain proposed. All other ADR statuses are
unchanged. SCI-02, SCI-03 and SCI-METRIC-02 remain open. `paper_exact:false`
and `receiver_enabled:false` remain unchanged. No SNR sweep, matched M2
comparison, power analysis, or validated gain claim was performed.

## M5g вЂ” proposed preregistration design (no experiment run)

Created the proposed study protocol and non-executable JSON draft. Audited the
M5f raw records and preserved its result: B had zero observed errors; C had
189/768 bit errors and 181/384 symbol errors, with C worse in all 12 pairs.
No stochastic pilot, Monte Carlo, sweep, tuning, or receiver/kernel change was
made. The draft's sample-size gate remains BLOCKED pending an approved
absolute DeltaBER interval half-width, compute budget, and independent pilot
variation.

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **677 passed in 3.44s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 111 files already formatted |
| M5g draft JSON parse/round-trip and gamma calibration check | PASS вЂ” proposed status/non-executable flag, distinct six seed namespaces, and `sigma_squared=4aВІ/gamma` verified |

M5g changes only experiment-design documentation and a non-executable draft;
ADR statuses are unchanged, SCI-02/SCI-03/SCI-METRIC-02 remain open, and
`paper_exact:false`, `receiver_enabled:false` remain unchanged.

## M5h-prep вЂ” validated independent pilot execution preparation

Added `evaluation/m5h_pilot_protocol.py`, an explicit candidate
`configs/m5h_pilot_draft.json`, focused tests, and the M5h preparation
contract. The config remains `design_status="proposed"` and
`execution_authorized=false`. The runner checks those gates before deriving
run streams or invoking the injected executor. Tests verify the rejected
configuration makes zero callback/decoder calls; a separate all-failure stub
test verifies 120 exception records are retained and pooled metrics are
blocked without generating data or invoking a decoder.

The audit used the actual M5f/M5e paired-run and adaptive-diagnostic API
signatures and the ADR-014 bootstrap contract. Candidate parameters and
gamma-to-sigma conversion are validated, B/C parity and 8sps origins are
explicit, and SeedSequence child derivation is domain-separated across pilot,
evaluation, data, noise, and bootstrap namespaces. The sample-size formula is
an initial normal approximation only. Workload is 120 sequences, 30,720 TCM
symbols, 61,440 information bits, 245,760 samples, and at least 240 decoder
passes; no runtime or memory estimate was made.

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS вЂ” **690 passed in 3.45s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 113 files already formatted |
| `python -m pytest -q tests/test_m5h_pilot_protocol.py --basetemp .pytest-m5h-focused-temp -p no:cacheprovider` | PASS вЂ” **13 passed** |

One intermediate exact pytest invocation could not remove the pre-existing
basetemp directory (WinError 5), producing 680 passed and 10 setup errors.
After permission to recreate that requested temp path, the exact full command
passed as recorded above. The first full run before that permission issue also
passed 690 tests. No pilot, new Monte Carlo, sweep, tuning, benchmark, or new
BER/SER evidence was run. M5f files/counts/warnings, ADR statuses, open SCI
questions, M1вЂ“M3, B4/B5 kernels, `paper_exact:false`, and
`receiver_enabled:false` remain unchanged. No new ADR is proposed.


## M5h-run ? authorized independent planning pilot (2026-10-29)

The explicitly authorized `m5h_pilot_only` run completed before this verification: 120/120 valid paired runs (30 per effective discrete gamma_b stratum), 0 numerical failures, 360 diagnostic/receiver decode calls. The full results, counts, resource measurements, bootstrap intervals, and limitations are in `docs/M5_INDEPENDENT_PILOT_REPORT.md`; machine-readable pilot-only outputs are under `outputs/m5h_independent_pilot/`. M5g/M5h proposed drafts and M5f artifacts were preserved. The run was not confirmatory and provides no performance claim.

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS ? **697 passed in 4.25s** |
| `ruff check src tests` | PASS ? All checks passed |
| `ruff format --check src tests` | PASS ? 115 files already formatted |

Observed pilot resources: 251.0627 s wall time; sampled peak worker RSS 46,190,592 bytes over 1,002 samples at 0.25 s intervals (monitoring, not a hard OS cap); 5,917,519-byte output. Pilot summary and config fingerprints are recorded in the report. These verification commands do not run a pilot or generate stochastic received signals.


## M5i ? pilot-informed confirmatory design preparation (2026-10-29)

Added the non-executable M5i confirmatory design draft, deterministic 100-ID future-evaluation seed manifest, evaluation-only validator/guard, tests, and `docs/M5_CONFIRMATORY_DESIGN_CONTRACT.md`. The M5h primary pilot variability was recomputed from its saved 30 primary checkpoints and matched the stored summary (`s_d=0.053093594133490844`, `R_approx=28`). The design candidate recommends R=100 with epsilon=0.02 as a precision target only. M5i remains `design_status="proposed_confirmatory"`, `execution_authorized=false`, `execution_scope="none"`; M5j requires a separate immutable run-specific user approval.

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS ? **715 passed in 3.74s** |
| `ruff check src tests` | PASS ? All checks passed |
| `ruff format --check src tests` | PASS ? 117 files already formatted |
| `python -m pytest -q tests/test_m5i_confirmatory_design.py --basetemp .pytest-m5i-green-temp -p no:cacheprovider` | PASS ? **18 passed** |

The manifest contains planned IDs and domain-separated evaluation seed provenance only; tests verified all 100 IDs, no seed overlap with the saved M5h pilot checkpoints, exact draft/code fingerprints, and a zero-callback execution guard. M5i generated no bits, received data, noise, decoder output, bootstrap replicates, or BER evidence. M5f and M5h historical artifacts were not modified. No M1-M3 or B4/B5 mathematical code was changed; accepted ADR statuses, open SCI questions, `paper_exact:false`, and `receiver_enabled:false` remain unchanged.

## M5j authorized confirmatory evaluation (2026-10-29)

M5j was separately authorized and ran only the frozen 100-sequence, 5 dB effective discrete gamma_b design. The full outcome, CI, caveat on post-summary worker exit code, output inventory, code/config fingerprints, and RSS monitoring semantics are in `docs/M5_CONFIRMATORY_EVALUATION_REPORT.md`. The run completed 100/100 with zero numerical failures. The persisted summary and all raw checkpoints were independently re-aggregated; all six bootstrap intervals were independently recomputed from checkpoint counts and matched. Wall time was 149.5761 s; sampled peak worker RSS was 47,329,280 bytes over 597 samples at 0.25 s intervals (periodic monitoring, not hard enforcement). The execution worker returned exit code 1 only after writing the complete summary because its final console print requested the obsolete `failure_count` field; the parent retained and verified the output. No rerun occurred.

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` | PASS ? 721 passed in 3.89s |
| `ruff check src tests` | PASS ? All checks passed |
| `ruff format --check src tests` | PASS ? 119 files already formatted |

## M6a вЂ” causal estimator trace instrumentation (2026-10-30)

Added the evaluation-only B4d history adapter, paired frozen/adaptive trace
comparison, independent manual [A](1)/posterior oracles, deterministic clock,
causality, immutability, and segmented-continuation tests. Fixtures use literal
complex sample arrays and noiseless real-gain constructions; no seeded or
random observations, M5j/M5h executions, tuning, SNR sweep, or performance
estimation were run. M5f/M5h/M5j hashes remained unchanged. Receiver and
estimator mathematical kernels were not edited.

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp .pytest-m6a-final-temp -p no:cacheprovider` | PASS вЂ” **748 passed in 9.83s** |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 122 files already formatted |

A later reuse of `.pytest-m6a-temp` hit Windows `WinError 5` during pytest
temporary-directory cleanup (729 passed, 19 setup errors). That directory was
left untouched; the complete verification above used a fresh
`.pytest-m6a-final-temp` and passed.

`M5j historical per-symbol trace unavailable` remains the status. M6a adds no
performance evidence or new ADR; SCI-02, SCI-03, and SCI-METRIC-02 remain open,
with `paper_exact:false` and `receiver_enabled:false` unchanged.

## M6b-prep вЂ” fresh-seed trace protocol (2026-10-30)

Added the proposed isolated diagnostic config, pure validation/serialization
protocol, synthetic schema round-trip and blocked-execution tests, plus protocol
and H1-H8 matrix documentation. The draft remains proposed/unauthorized/scope
none. No RNG stream, data/noise, receiver callback, M6b run, M5j/M5h execution,
tuning, or BER/SER evidence was created. Historical output hashes were checked
by the repository integrity tests and remain unchanged. Receiver mathematics
and accepted ADR statuses were not changed. Full verification follows below.

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_m6b_trace_protocol.py --basetemp .pytest-m6b-prep-focused-5-temp -p no:cacheprovider` | PASS вЂ” 12 passed in 0.59s |
| `python -m pytest -q --basetemp .pytest-m6b-prep-final-2-temp -p no:cacheprovider` | PASS вЂ” 760 passed in 5.63s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 124 files already formatted |

The full suite includes `test_m5f_m5h_and_m5j_historical_outputs_keep_baseline_bytes`; it passed against the documented M5f/M5h/M5j baseline digests. M6b tests use synthetic trace payloads and an authorization spy only. No M6b RNG stream, data/noise, receiver callback, or output directory was created. The M6b source AST test confirms no receiver import or random generator/sample call is present in the protocol module.

Final verification after the trace provenance and immutability assertions were complete (supersedes the earlier M6b-prep timing above):

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_m6b_trace_protocol.py --basetemp .pytest-m6b-prep-focused-6-temp -p no:cacheprovider` | PASS вЂ” 12 passed in 0.48s |
| `python -m pytest -q --basetemp .pytest-m6b-prep-final-3-temp -p no:cacheprovider` | PASS вЂ” 760 passed in 6.83s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 124 files already formatted |

## M6b-run вЂ” authorized trace diagnostic (2026-10-30)

Preflight validated the separate approved snapshot against the unchanged M6b
preparation draft, including exact science, policy, clock, seed, and schema
fields. Pre-run protocol/trace tests, deterministic B4d causal tests, and the
M5f/M5h/M5j baseline hash test passed. Exactly run-001 through run-003 then
completed with 192 B/C symbol rows, shared received hashes, one B5b decode per
mode, and no numerical failures. No M5j/M5h rerun, Monte Carlo, tuning, or
performance inference occurred.

| Command / check | Result |
|---|---|
| `python -m pytest -q tests/test_m6b_trace_protocol.py --basetemp .pytest-m6b-run-preflight-temp -p no:cacheprovider` | PASS вЂ” 13 passed in 0.34s |
| `python -m pytest -q tests/test_m5k_read_only_audit.py::test_m5f_m5h_and_m5j_historical_outputs_keep_baseline_bytes --basetemp .pytest-m6b-hash-preflight-temp -p no:cacheprovider` | PASS вЂ” 1 passed in 0.31s before run; same baseline test passed in full suite after run |
| `python -m pytest -q tests/test_reconstruction_causal_trace.py --basetemp .pytest-m6b-causal-preflight-temp -p no:cacheprovider` | PASS вЂ” 20 passed in 0.77s |
| `python -m pytest -q --basetemp .pytest-m6b-run-final-temp -p no:cacheprovider` | PASS вЂ” 761 passed in 6.63s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 125 files already formatted |

Execution took 0.6959 s. RSS sampling was attempted periodically but Windows
`GetProcessMemoryInfo` failed with error 6; peak RSS is unavailable and the
512 MiB budget is unverified. No value was estimated. Runtime code fingerprint,
approved/draft config hashes, and per-file output hashes are in the M6b output
manifest; the output tree has 25 checked files and digest
`19b58bd057ffc1c8b725b225f4698a26b120c88dec6950fbaecd058c206a9ba3`.
Post-run verification matched the runtime source fingerprint, both config
fingerprints, all 25 output-file hashes, and the historical M5f/M5h/M5j baseline
integrity test. Receiver mathematics, M5j data/results, accepted ADRs, and open
SCI statuses were not changed.

## M6c вЂ” source-equation audit verification (2026-10-30)

The new `tests/test_m6c_source_equation_audit.py` contains fixed-vector
algebra controls only. It creates no random bits/noise, invokes no receiver
sequence or B5 decode, and writes no M5/M6b artifacts. It independently
checks [A](5) signs/order at eight angles; unequal/equal/zero/negative
coefficients; ADR-012 complex-to-IQ identity and literal sample mean; a
scalar-loop one-step [A](1) oracle; weighted-residual identity over 16
hypotheses; posterior normalization/first-edge/continuation behavior; and the
literal M1/ADR-002 edge-phase table.

| Command / check | Result |
|---|---|
| `python -m pytest -q tests/test_m6c_source_equation_audit.py --basetemp .pytest-m6c-focused-final2-temp -p no:cacheprovider` | PASS вЂ” 9 passed in 0.17s |
| `python -m pytest -q --basetemp .pytest-m6c-final-temp -p no:cacheprovider` | PASS вЂ” 770 passed in 4.99s |
| `python -m pytest -q tests/test_m5k_read_only_audit.py::test_m5f_m5h_and_m5j_historical_outputs_keep_baseline_bytes --basetemp .pytest-m6c-historical-final-temp -p no:cacheprovider` | PASS вЂ” 1 passed in 0.21s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 126 files already formatted |

The M5f/M5h/M5j baseline-hash test also passed within the full suite. A
read-only check of the M6b `integrity.json` manifest found all 25 listed file
SHA-256 values unchanged; its recorded output-tree digest remains
`19b58bd057ffc1c8b725b225f4698a26b120c88dec6950fbaecd058c206a9ba3`. No
historical numerical result or receiver/scientific implementation changed.
No Monte Carlo, M6b rerun, new observations, or tuning ran.

Final-state rerun after all M6c documentation updates:

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp .pytest-m6c-final-verification-temp -p no:cacheprovider` | PASS вЂ” 770 passed in 5.20s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 126 files already formatted |

The separate M5f/M5h/M5j hash regression passed again (1 passed in 0.21s).
The M6b output integrity check again matched all 25 per-file hashes and the
recorded tree digest exactly.

## M6d вЂ” source-evidence dossier verification (2026-10-30)

Added `configs/m6d_source_evidence_matrix.json` as a provenance/evidence
ledger, not a receiver configuration and not an author-confirmed mapping.
`tests/test_m6d_source_evidence.py` checks JSON round-trip, exact source/page
fingerprints, all 16 unique project transitions against the current project
trellis and ADR-002 phase helper, valid 0вЂ¦7 phases, project/source status
separation, absence of unsupported `AUTHOR_CONFIRMED` entries, explicit
locators, unresolved mapping flags, unchanged scientific flags and approved
historical config hashes, and all M6b per-file/tree hashes. The tests only read
the evidence artifacts and static project trellis/labeling API; they have no
random-data, noise, receiver-sequence, or evaluation calls.

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_m6d_source_evidence.py --basetemp .pytest-m6d-evidence-temp -p no:cacheprovider` | PASS вЂ” 7 passed in 0.05s |
| `python -m pytest -q tests/test_m5k_read_only_audit.py::test_m5f_m5h_and_m5j_historical_outputs_keep_baseline_bytes --basetemp .pytest-m6d-historical-temp -p no:cacheprovider` | PASS вЂ” 1 passed in 0.21s |
| `python -m pytest -q --basetemp .pytest-m6d-final-temp -p no:cacheprovider` | PASS вЂ” 777 passed in 5.26s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 127 files already formatted |

The full suite also ran the historical M5f/M5h/M5j byte-integrity regression.
The focused M6d evidence test independently checked all 25 M6b output hashes
and the recorded tree digest. No historical output, scientific configuration,
receiver code, mathematical kernel, or ADR status changed. No observations or
performance data were generated.

Repository-root Ruff checks were also attempted per the workspace instructions.
`ruff check .` exited 0 with вЂњAll checks passedвЂќ while reporting access-denied
warnings for protected paths. `ruff format --check .` reached 205 paths and
then the installed Ruff process panicked with `Expected a ruff source file`;
the scoped required check `ruff format --check src tests` passed above. No
historical or protected files were modified during these checks.

## M6e вЂ” deterministic update intervention audit (2026-10-30)

`tests/test_reconstruction_update_intervention.py` uses explicit deterministic
arrays only. Its scalar oracle is independent of `paper_recursion.py`; it
checks the actual update API, [A](5) delta identity, 16 project edge alignment,
ADR-005 metric deltas and expanded squared-residual identity, fixed-prior
posterior response, nonzero symbol/sample/tick origins, immutability, finite
value validation, and absence of reference/truth/RNG operands. No receiver
sequence, decoder, noise generation, or historical output write occurs.

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_reconstruction_update_intervention.py --basetemp .pytest-m6e-tolerance-temp -p no:cacheprovider` | PASS вЂ” 11 passed in 0.19s |
| `ruff check src/hf_tcm/evaluation/reconstruction_update_intervention.py tests/test_reconstruction_update_intervention.py` | PASS вЂ” All checks passed |
| `ruff format --check src/hf_tcm/evaluation/reconstruction_update_intervention.py tests/test_reconstruction_update_intervention.py` | PASS вЂ” 2 files already formatted |
| `python -m pytest -q --basetemp .pytest-m6e-final-verified-temp -p no:cacheprovider` | PASS вЂ” 788 passed in 5.45s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 129 files already formatted |
| Historical M5f/M5h/M5j and M6b hash regression tests | PASS вЂ” 2 passed in 0.21s |

The targeted historical checks confirmed M5f/M5h/M5j baseline bytes and all
M6b trace hashes. No historical artifact is an output target of the new
adapter. The full suite used only existing deterministic tests/fixtures; M6e
generated no noise, receiver sequences, or BER evidence.

## M6f вЂ” deterministic two-symbol factorial ablation (2026-10-30)

`tests/test_reconstruction_factorial_ablation.py` runs only fixed 16-sample
complex arrays. It tests the four immutable B/A/K/C M5j policy constants,
shared first-symbol metrics/posterior/innovation, an independent scalar [A](1)
oracle and factorial state identity, actual B4d second-symbol carry-forward,
independent 16-edge predictions/metrics and squared-residual interaction,
actual continuation and separate common-prior posterior contrasts, derived-q
provenance, zero-innovation behavior, clock origins/cutoffs, first-row
immutability under a second-window perturbation, and the no-reference/no-truth/
no-RNG evaluation boundary. It invokes no full decoder and computes no BER.

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_reconstruction_factorial_ablation.py --basetemp .pytest-m6f-focused-final-temp -p no:cacheprovider` | PASS вЂ” 9 passed in 0.32s |
| `python -m pytest -q --basetemp .pytest-m6f-final-temp -p no:cacheprovider` | PASS вЂ” 797 passed in 5.46s |
| `python -m pytest -q tests/test_m5k_read_only_audit.py::test_m5f_m5h_and_m5j_historical_outputs_keep_baseline_bytes tests/test_m6d_source_evidence.py::test_historical_configs_and_m6b_trace_hashes_remain_unchanged --basetemp .pytest-m6f-historical-temp -p no:cacheprovider` | PASS вЂ” 2 passed in 0.21s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 131 files already formatted |

The full suite and explicit historical checks matched the existing M5f/M5h/M5j
and M6b integrity baselines. The test adapter writes no evaluation outputs.
No stochastic data, channel/noise realization, decoder path, or BER/SER
evidence was created; no production receiver mathematics or ADR changed.

## M6g вЂ” deterministic multistep posterior-feedback audit (2026-10-30)

Added the evaluation-only multistep feedback adapter, deterministic tests,
and report. Tests use the exact declared 64-sample formula fixture and a
clock-offset variant. CLOSED_LOOP invokes the existing B4d sequence API for
each fixed arm; COMMON_OPERAND first freezes the complete eight-value B
innovation vector, then uses an isolated scalar A(1) replay with production
candidate-metric and posterior functions. Independent scalar tests cover all
rows, priors, metrics, innovations, state updates, interactions, and clocks.
There is no RNG, encoder/channel generation, decoder, BER/SER calculation,
parameter search, or historical output write.

| Command | Result |
|---|---|
| python -m pytest -q tests/test_reconstruction_multistep_feedback_audit.py --basetemp .pytest-m6g-focused-final3-temp -p no:cacheprovider | PASS вЂ” 12 passed in 1.87s |
| python -m pytest -q --basetemp .pytest-m6g-final3-temp -p no:cacheprovider | PASS вЂ” 809 passed in 7.02s |
| ruff check src tests | PASS вЂ” All checks passed |
| ruff format --check src tests | PASS вЂ” 133 files already formatted |
| M5f/M5h/M5j historical baseline and M6b hash regression tests | PASS вЂ” 2 passed in 0.22s |

Historical integrity regressions confirmed the M5f/M5h/M5j output baseline and
all M6b config/trace hashes unchanged. The M6g fixture hash is
99df8784d417cd9d615c389d088f717f0735f4af6accb282fcff82a547629969. No
scientific or production receiver mathematics, accepted ADR, or open SCI
status changed. These are deterministic algorithmic diagnostics, not
performance or M5j causal evidence.

All per-symbol diagnostic rows were serialized in canonical B/A/K/C and
CLOSED_LOOP/COMMON_OPERAND order to the separate M6g namespace. JSON size is
206,378 bytes and its SHA-256 is
67a48243f4fd43a104584004ec98f5aa7c2a08c6b3b14aed20372fc8e3426a75.

## M6h deterministic posterior-clamp ablation (2026-10-30)

Added an evaluation-only same-state posterior-weight swap and a separate
multistep replay that retains each arm's own posterior history while using
same-symbol frozen-B weights only in the correction operand. The fixed M6g
fixture and its recorded B/A/K/C CLOSED_LOOP/COMMON_OPERAND arrays are read
only. The adapter recomputes only deterministic predictions, metrics,
posteriors, and update contrasts on the fixture; it uses no RNG, decoder,
reference bits, channel truth, or BER/SER computation. The new trace is
separate at `outputs/m6h_posterior_clamp/deterministic_trace.json` (428,461
bytes, SHA-256
`14bb8e891f5da49b5374804374e9fd1d28d32cbc74404e062651741708946e9f`). M6g
remains byte-identical (SHA-256
`67a48243f4fd43a104584004ec98f5aa7c2a08c6b3b14aed20372fc8e3426a75`).

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_reconstruction_posterior_clamp_audit.py --basetemp .pytest-m6h-focused-final-temp -p no:cacheprovider` | PASS вЂ” 9 passed in 1.07s |
| `python -m pytest -q --basetemp .pytest-m6h-final-temp -p no:cacheprovider` | PASS вЂ” 818 passed in 14.43s |
| `python -m pytest -q tests/test_m5k_read_only_audit.py::test_m5f_m5h_and_m5j_historical_outputs_keep_baseline_bytes tests/test_m6d_source_evidence.py::test_historical_configs_and_m6b_trace_hashes_remain_unchanged --basetemp .pytest-m6h-historical-final-temp -p no:cacheprovider` | PASS вЂ” 2 passed in 3.61s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 135 files already formatted |

H2-H4 source conventions, H5 author mapping, H7/H8 model contributions, and
M6h-to-M5j causal contribution remain unresolved. No ADR or receiver
mathematics changed; `paper_exact:false` and `receiver_enabled:false` remain.

## M7a proposed policy-study design (2026-10-30)

Added `configs/m7a_policy_study_draft.json`, a strict evaluation-side design
validator/authorization guard, a deterministic test module, and the M6
synthesis / M7 design documentation. The validator accepts only the fixed
nine-arm 3x3 grid and proposed profile, checks sigma scaling, partitions and
distinct new data/noise/bootstrap/experiment-metadata roots, paired-buffer
contract, selection/failure/ADR-014 rules, workload accounting, and
`execution_authorized=false`. The guard blocks before any injected callbacks;
tests spy on the RNG/data/noise/decoder boundary. No seed children were
derived, no RNG was instantiated, and no bits, noise, received buffers,
decoder calls, or performance statistics were generated.

The expected unique one-pass-per-policy workload is TRAIN 360, VALIDATION
80, and future FINAL 200 policy decoder passes. `run_adaptive_estimator_diagnostic`
currently executes one decoder pass for each of its two modes per paired
call. A naive training loop over the eight non-B candidates would therefore
make 640 decoder passes, repeating B 280 times; an evaluation-side M7b grid
orchestrator would need to reuse each sequence's B result to meet the 360
unique-pass target. That implementation choice and resource budget are
explicit M7b gates. Optional historical-C descriptive arms add 40 validation
or 100 final decodes. No runtime/RSS estimate is asserted.

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_m7a_policy_study_design.py --basetemp .pytest-m7a-focused-final2-temp -p no:cacheprovider` | PASS вЂ” 23 passed in 0.29s |
| `python -m pytest -q --basetemp .pytest-m7a-final-temp -p no:cacheprovider` | PASS вЂ” 841 passed in 9.76s |
| `python -m pytest -q tests/test_m5k_read_only_audit.py::test_m5f_m5h_and_m5j_historical_outputs_keep_baseline_bytes tests/test_m6d_source_evidence.py::test_historical_configs_and_m6b_trace_hashes_remain_unchanged tests/test_reconstruction_multistep_feedback_audit.py tests/test_reconstruction_posterior_clamp_audit.py --basetemp .pytest-m7a-historical-temp -p no:cacheprovider` | PASS вЂ” 23 passed in 3.97s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 137 files already formatted |

M5f/M5h/M5j, M6b, M6g, and M6h historical outputs passed their exact hash
checks. No scientific code, receiver mathematics, ADR, or SCI status changed.
M7a is READY as a proposed design and BLOCKED for execution; later partitions
are not automatically chained.

## M7b authorized TRAIN policy selection (2026-10-30)

Added a run-specific TRAIN-only config, evaluation-side 9-policy
orchestration that invokes the existing B4d/B5b path once per candidate, raw
checkpoint replay/selection verification, targeted deterministic tests, and
the M7b report. The original M7a draft is unchanged. The exact 40 TRAIN IDs
and M7a-derived TRAIN seed provenance are frozen in the approved snapshot
and manifest. One received realization per sequence was reused by all nine
policies. No validation/final RNG or receiver execution occurred.

The completed partition contains 40 unique received hashes, 360 policy
records, 360 decoder invocations, 92,160 policy-symbol passes, 20,480
information bits, and zero policy failures. Independent verification
recomputed all raw errors from saved evaluation-side bits and decoded
outputs, confirmed exact denominators and ranking, and selected frozen B
(`a100_k000`). The state is `TRAIN_SELECTED_NOT_VALIDATED`; the result is
selection-biased training evidence only. Wall-clock was 174.07 s; periodic
RSS monitoring observed 43,401,216 bytes, which is not a hard OS limit.
Historical M5f/M5h/M5j/M6b/M6g/M6h hashes remained equal to their pre-run
baselines.

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_m7b_train_runner.py -p no:tmpdir -p no:cacheprovider` | PASS вЂ” 5 passed in 1.89s |
| `python -m pytest -q --basetemp .pytest-m7b-final-temp -p no:cacheprovider` | PASS вЂ” 846 passed in 9.39s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 139 files already formatted |

The selected policy and exact ranking are in
[`M7_TRAIN_POLICY_SEARCH_REPORT.md`](M7_TRAIN_POLICY_SEARCH_REPORT.md).
M7c remains blocked: frozen B won, so a validation pair would be B versus B
unless separately redesigned around an explicit reproducibility estimand.
No receiver mathematics, ADR status, or open SCI status changed.

## M7c closeout and M8a preparation (2026-10-30)

M7b's 40 saved checkpoints were independently replayed read-only: 40 unique
run IDs and received hashes, nine complete candidate records per run, 360
records and decoder passes, zero failures, and denominators of 20,480 bits
and 10,240 symbols per candidate. Recounted integer totals reproduce frozen
B (`a100_k000`) as the TRAIN winner. The original status remains
`TRAIN_SELECTED_NOT_VALIDATED`; M7 validation was not run because it would be
B versus B. No validation/final RNG was used. M7b's 46-file integrity
manifest and the pre-M7 historical tree baseline still match.

M8a adds an unauthorized proposed anchored profile, exact eight-arm design,
distinct ungenerated M8 partition roots, and an evaluation-only validator
whose guard blocks before RNG/data/receiver callbacks. Deterministic B4c
fixtures check same initial full estimates/metrics/posteriors, zero-anchor
geometric decay, constant anchored K=0 state, alpha=1 recentering invariance,
and causal sample cutoffs. No stochastic data, decoder study, M8 output, ADR,
or receiver-mathematics change was made. M8a draft SHA-256:
`0740500746cfc340207d3b30a9e9cc62209e620c6a108926b1623cd7e46d960c`.

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp .pytest-m8a-final-verify-temp -p no:cacheprovider` | PASS вЂ” 868 passed in 9.63s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 141 files already formatted |

`paper_exact:false`, `receiver_enabled:false`, accepted ADRs, and open
SCI-02/SCI-03/SCI-METRIC-02 remain unchanged. At the time of M8a preparation,
M8b was blocked pending separate TRAIN-only authorization and run-specific
approval; the later authorized attempt is recorded below.

## M8b authorized TRAIN attempt (2026-10-30)

The M8b authorization covered TRAIN only. The frozen M8a draft hash matched
its sidecar; the run-specific config hash was
`a081e98bcbdf6aab94175fe410f5161e06e72d24ad99070147172088c7945e95`. The
attempt generated 40 TRAIN bit/noise inputs and checkpoints, but all eight
policy calls per run failed before the receiver because the runner indexed a
missing `clock_origins` key. Independent checkpoint replay found 40 unique run
IDs/hashes, 320 explicit failures, zero decoder invocations, no eligible
candidate, and no selection. No validation/final seeds were generated or used.
This is `TRAIN_INCOMPLETE_OR_BLOCKED`, not a BER result.

The post-attempt runner correction changed its source fingerprint, so the
original approved config cannot authorize a resume. The M8b output manifest,
M5f/M5h/M5j/M6b/M6g/M6h/M7b trees, M8a draft, and M8a sidecar all verified
unchanged. Actual failed-attempt wall time was 0.1352429 s; periodic RSS was
37,306,368 bytes. These are not completed-study resource measurements.

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp .pytest-m8b-final-temp -p no:cacheprovider` | PASS вЂ” 876 passed in 10.29s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 143 files already formatted |

The targeted M8a/M8b preflight suite also passed: 30 tests. Tests used
deterministic fixtures/mocks and did not launch a second TRAIN or generate
stochastic observations. The M8b report is
[`M8_ANCHORED_TRAIN_REPORT.md`](M8_ANCHORED_TRAIN_REPORT.md).

## M8b controlled technical recovery (2026-10-30)

The original failed M8b attempt and its 40 received hashes remain unchanged.
The recovery preflight reproduced the missing `clock_origins` failure on the
old draft lookup, resolved clocks from the accepted receiver config/B4d
independent-sequence contract, and passed a real deterministic conditional
decode smoke for all eight policies. Same-seed replay then matched all 40
original received hashes before decoding and completed 320/320 policy
decodes. Independent checkpoint recomputation selected historical frozen B;
status is `TRAIN_SELECTED_NOT_VALIDATED`. Validation/final streams were not
derived or used. Full details are in
[`M8_TRAIN_RECOVERY_REPORT.md`](M8_TRAIN_RECOVERY_REPORT.md).

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp tmp/pytest-m8b-recovery-final-temp -p no:cacheprovider` | PASS вЂ” 883 passed in 10.55s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 145 files already formatted |

The pytest basetemp is fresh and workspace-local under `tmp/`; root-level
`.pytest-*` basetemps were denied by Windows ACLs at session cleanup and were
left untouched. The recovery took 159.352 seconds in one process. Periodic
RSS observed 44,167,168 bytes; this is monitoring, not a hard OS limit. No
receiver mathematics, ADR status, or historical M5/M6/M7/M8 outputs changed.

## M8c closeout / M9a design preparation (2026-10-30)

Read-only verification of the immutable M8 recovery checkpoint set found 40
unique sequence IDs and received hashes, eight complete policy outputs per
sequence, 320 decoder calls, no failures, and the original frozen-B TRAIN
winner. Raw checkpoint totals independently reproduce B (413/20,480 bits;
371/10,240 symbols), runner-up `anch_a085_k025` (429/20,480;
385/10,240), and historical C (7,804/20,480; 7,074/10,240). The separate
post-selection paired audit and its ADR-014 bootstrap did not alter recovery
outputs. The M9a draft validator/guard uses no data, receiver, or decoder
callbacks; M9 remains proposed and unauthorized.

| Command | Result |
|---|---|
| `python -m pytest -q --basetemp tmp/pytest-m9a-final-temp -p no:cacheprovider` | PASS вЂ” 890 passed in 11.00s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format src/hf_tcm/evaluation/m9a_fixed_policy_study_design.py tests/test_m9a_fixed_policy_study_design.py` | PASS вЂ” 2 files reformatted after initial check |
| `ruff format --check src tests` | PASS вЂ” 147 files already formatted |

No M9 evaluation, RNG/data/noise generation, or decoder invocation occurred.
M5f/M5h/M5j/M6b/M6g/M6h/M7b/M8 outputs and M8a/original M8b configuration
artifacts remain immutable. `paper_exact:false`, `receiver_enabled:false`,
accepted/proposed ADRs, and open SCI questions are unchanged.

## M9b fixed-policy evaluation (2026-10-30)

The M9a draft remained unchanged at SHA-256
`a6be31a2225aeaee48fffec5ff6f868866773a1087978a561e4cadea78e1d5ac`. The
separate approved M9b snapshot SHA-256 was
`72dcc41f8cfc20028a1c2ea0ea15d0edc3fc6d941a322a3622e58ae1b099cad4`; its
runtime source fingerprint was
`93530a40e4c95d24324150da37c423dfbbfc4945ddf4a9e80b0b154d987f04c1`. The
pre-execution real receiver smoke passed. Execution completed 100/100 paired
runs, 200 policy records and experimental decoder calls, 100 unique received
hashes, and zero failures. Independent checkpoint recount and scalar-loop
bootstrap verification passed. Historical M5вЂ“M8 hashes and the M9a draft
remained unchanged. The observed point contrasts were DeltaBER
`-0.0011328125` and DeltaSER `-0.0019140625`; both 95% paired cluster
bootstrap intervals included zero. Full scientific interpretation is in
[`M9_FIXED_POLICY_EVALUATION_REPORT.md`](M9_FIXED_POLICY_EVALUATION_REPORT.md).

| Command | Result |
|---|---|
| `python -m pytest -q -x --tb=short --basetemp tmp/pytest-m9b-first-error-temp -p no:cacheprovider` | PASS вЂ” 897 passed in 11.82s |
| `python -m pytest -q --basetemp tmp/pytest-m9b-preflight3-temp -p no:cacheprovider tests/test_m9b_fixed_policy_evaluation_runner.py` | PASS вЂ” 7 passed in 1.48s |
| `python -m pytest -q --basetemp tmp/pytest-m9b-final-temp -p no:cacheprovider` | PASS вЂ” 897 passed in 11.31s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 149 files already formatted |

An earlier full pytest attempt hit Windows `WinError 5` during pytest basetemp
cleanup; that ACL-restricted directory was left untouched. The complete suite
then passed on a fresh workspace-local basetemp. M9 experimental wall time was
102.5633079999825 s; bootstrap computation took 0.21279959997627884 s.
Periodic RSS peaked at 50,085,888 bytes (monitoring only, not a hard OS limit).
No receiver mathematics or ADR status changed. No validation, final,
variable-channel, or other RNG partition was used.

## M9 closeout and M10a design preparation

M9b checkpoint counts were independently recounted: 100 unique runs and
received hashes, 200 valid paired policy records/decoder calls, and zero
failures. Recomputed raw totals and ADR-014 bootstrap bounds matched the saved
verification. Anchored point estimates were lower; both intervals included
zero. No new observations were generated.

M10a added a deterministic evaluation-side gain schedule adapter, an
unauthorized design validator and tests, a proposed M10b JSON draft with
SHA-256 sidecar, and scientific/statistical design documents. Its deterministic
integration test exercises both fixed policies across P0/P1/P2 on explicit
waveform/noise arrays; it does not initialize RNG or create stochastic
samples. No production channel, receiver, or estimator mathematics changed.
ADR-016 was subsequently accepted for evaluation-side use only; M10b then ran
under a separate approved snapshot.

M10a final verification:

| Command | Result |
|---|---|
| `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-m10a-first-error-temp -p no:cacheprovider` | PASS вЂ” 918 passed in 14.53s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 153 files already formatted |

Two full-suite invocations reached Windows `WinError 5` in pytest's session
cleanup on their fresh basetemps and did not yield usable summaries. Those
directories were not deleted. A later complete run passed on a new
workspace-local basetemp; no ACL-restricted directory was removed.

Read-only M9b replay using saved checkpoints returned
`M9_EVALUATION_COMPLETE_VERIFIED` (100 runs/hashes, 200 records/decoder calls,
zero failures); current output hashes match its immutable integrity manifest.
Recomputed ADR-014 bootstrap bounds and the independent scalar oracle match the
saved bounds. The approved M9 historical baseline, covering M5 through M9a
inputs, still matches current artifacts. No M10 random stream or stochastic
observation was created during M10a.

## M10 GATE A / M10b verification

ADR-016 accepted `controlled_piecewise_real_gain_v1` solely for evaluation-
side channel generation/analysis. The immutable M10a draft SHA-256 remained
`80ec2ea30e04bfeb02508380b94f29bb08140a1906fa61816d137ed56798066f`. The
approved M10b snapshot SHA-256 is
`a43c5109f58ce8aab75f8c8bac6d8daab648932351bdd6be70942484b4d88b84`; runtime
source fingerprint is
`918a4ad3538c84536f092a80f318a0e3df1c87518667ae2bd0edfc380439b661`.

The deterministic real-receiver preflight passed for six profile/policy
invocations plus direct API comparisons and causal-cutoff checks. M10b then
completed exactly 100 run clusters, 300 received profile buffers, 600 policy
records and 600 decoder calls, with zero policy failures. A runner's initial
recount incorrectly compared planned seed records (`initialized=false`) to
executed data/noise checkpoint flags (`initialized=true`); the original
failure record was preserved. A separate read-only audit reproduced all bits
and noise from the approved seeds and recounted decoded-array errors. It
verified 100 IDs, 300 received hashes, 600 records/calls, and the ADR-014
paired bootstrap. The final status is `M10_EVALUATION_COMPLETE_VERIFIED`.

Observed evaluation wall time was 296.58 s, bootstrap 0.17 s, and periodic
RSS peak 48,910,336 bytes (monitor only, not an OS hard limit). The primary
P1 DeltaBER was -0.0003125 with 95% interval
[-0.00205126953125, 0.0014453125], which includes zero. Historical M5вЂ“M9 and
M10a artifacts, approved config, decision sidecars, and the M10 output
integrity manifest were rechecked after documentation updates.

Final verification commands:

| Command | Result |
|---|---|
| `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-m10b-final-temp -p no:cacheprovider` | PASS вЂ” 927 passed in 22.60s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 157 files already formatted |

No ACL-restricted pytest directories were removed. No M9/M8/M7/M5 rerun,
validation/final partition, or additional experiment was executed.

## M11a Interactive Demo Studio

Implemented a standard-library localhost web UI and deterministic evaluation-
side B4d/conditional-Viterbi trace collector. The demo uses explicit bit
patterns and deterministic noise fixtures only. It does not instantiate RNGs,
run Monte Carlo, or change receiver mathematics. Historical M5-M10 outputs are
read-only. The full stage/coverage limitations are listed in
`docs/M11_INTERACTIVE_DEMO_STUDIO_REPORT.md`; specifically stage 28 is partial
because one fixed demo frame cannot produce independent paired inference.

Verification:

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_m11a_demo_studio.py --basetemp .pytest-m11a-final-targeted-temp -p no:cacheprovider` | PASS вЂ” 6 passed in 1.69s |
| 
ode --check src/hf_tcm/studio/static/studio.js` | PASS |
| `python -m hf_tcm.demo_studio --no-browser --port 18766` + local HTTP GET/POST smoke | PASS вЂ” HTTP 200; metadata shows 28 stages, 4 states, 16 edges; GET did not invoke receiver; explicit 4-symbol/32-sample POST returned B+anchored traces with one Viterbi call each and no RNG |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 162 files already formatted |
| `python -m pytest -q --tb=short --maxfail=1 --basetemp .pytest-m11a-final-verification-temp -p no:cacheprovider` | PASS вЂ” 933 passed in 23.05s |

An earlier full-suite invocation on `.pytest-m11a-final-temp` emitted
intermittent setup errors and then hit `WinError 5` during pytest session
cleanup. That run was not treated as verification. A fresh workspace-local
basetemp completed all 933 tests successfully; the final post-change run on
`.pytest-m11a-final-verification-temp` passed 933 tests in 23.05s. Other fresh
basetemp attempts hit the known `WinError 5` during cleanup, so those runs were
not treated as verification. No old ACL-restricted temp directory was deleted.
Existing M7b, M8 recovery, M9b, and M10b integrity
manifests were read-only checked (306 manifest entries total, zero mismatches);
the full suite also passed the established M5f/M5h/M5j/M6b/M6g/M6h integrity
regressions. No historical output was written.

## M11b Demo Studio release verification

The existing dependency-free local UI was retained. Launch with
`python -m hf_tcm.demo_studio`. The explicit deterministic F=32 action uses 64
fixed bits, 8 samples/symbol, fixed noise, no RNG, two receiver configurations,
and one shared receive buffer. The 4-symbol smoke fixture remains available.

Real Microsoft Edge headless browser automation via DevTools Protocol verified
both 1366x768 and 1920x1080 viewports. The run action, six requested symbol
positions, all 28 stage details, graph and edge table synchronization,
parameter search, experiment dashboard, 18 presentation steps, and console
error state were checked. Screenshots are
`docs/screenshots/m11b-edge-1366x768.png` and
`docs/screenshots/m11b-edge-1920x1080.png`.

The generated `docs/DEMO_PARAMETER_COVERAGE.md` contains 28 actual-render audit
rows plus the complete 459-entry parameter inventory. Historical integrity
manifests for M6b, M7b, M8 recovery, M9b, and M10b were checked read-only:
331 entries, zero mismatches. The complete suite also exercises established
M5 historical hash regressions. No historical output was modified.

HTTP smoke at `127.0.0.1:18766` returned healthy metadata without invoking a
receiver on GET. Explicit F=32 POST returned 32 symbols and 256 samples,
`rng_used=false`, a shared receive hash, and one conditional Viterbi result per
receiver. An invalid bit payload returned HTTP 400 without invoking a receiver.
The UI has no cloud or remote analytics dependency and the server rejects
non-local bind addresses. Stage 28 paired inference remains PARTIAL BY DESIGN.

Final verification commands:

| Command | Result |
|---|---|
| `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-m11b-final-temp -p no:cacheprovider` | PASS - 942 passed in 26.30s |
| `ruff check src tests` | PASS - All checks passed |
| `ruff format --check src tests` | PASS - 162 files already formatted |
| 
ode --check src/hf_tcm/studio/static/studio.js` | PASS |

No ACL-restricted temporary directories were deleted. No production receiver,
encoder, metric, estimator, or Viterbi mathematics changed. No RNG,
Monte Carlo, new ADR, or M12 work was performed.

## M11c defense release freeze and rehearsal

The M11c release manifest records Python 3.13.13, NumPy 2.3.3, package
`hf-tcm-sim` 0.1.0, app/static-source hashes, deterministic fixture and shared
received-buffer fingerprints, 459-entry post-run parameter inventory, and
selected M5j/M7b/M8b-recovery/M9b/M10b summary hashes. Twenty-two declared
source/artifact hashes were rechecked with zero mismatches. Historical output
files and integrity manifests were not written. The live rehearsal screenshot
is `docs/screenshots/m11c-rehearsal-m9m10-1366x768.png`.

Windows launch helpers `start_demo.cmd` and `start_demo.ps1` use the existing
entrypoint, bind only to localhost, check Python/NumPy and port availability,
and never install packages. Startup, occupied-port, and missing-NumPy cases
were exercised. The Edge rehearsal at 1366x768 covered explicit F=32 execution,
symbols 0/15/31, all 16 selectable graph edges, graph/table synchronization,
actual runtime Inspector search, receiver comparison, M5-M10 dashboard, and
all 18 presentation steps. It was browser automation, not a human rehearsal.

The final explicit HTTP checks returned GET `/`=200, healthy status without a
receiver call, 28 stages, and a valid F=32 POST with 32 symbols, 256 samples,
`rng_used=false`, both receivers on the same received SHA-256, 459 runtime
parameter entries, and a 64-bit conditional Viterbi output per receiver.
Malformed bits returned HTTP 400. Stage 28 remains PARTIAL BY DESIGN for paired
inference from a single fixture. Offline readiness is established from local
dependencies and loopback-only implementation; a physically disconnected
machine was not tested.

Final M11c verification:

| Command | Result |
|---|---|
| `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-m11c-final-temp -p no:cacheprovider` | PASS вЂ” 944 passed in 25.59s |
| `ruff check src tests` | PASS вЂ” All checks passed |
| `ruff format --check src tests` | PASS вЂ” 162 files already formatted |
| 
ode --check src/hf_tcm/studio/static/studio.js` | PASS |

No ACL-restricted temporary directory was deleted. No receiver mathematics,
ADR, historical experiment, or scientific result changed. No RNG or Monte
Carlo ran, and M12 was not started.

## M11d accessibility and final acceptance вЂ” 2026-11-02

The independent Edge run passed **285 checks** and captured 36 screenshots at
1366Г—768 and 1920Г—1080. It covered the explicit deterministic F=32 POST,
Inspector categories, help-dialog keyboard/focus lifecycle, formula operands,
symbols, all four states and sixteen edges, conditional Viterbi, archived
plots, presentation screens, exports, and responsive layout. No browser
console errors, failed HTTP requests, external requests, or overflow occurred.
See `M11D_VISUAL_QA_REPORT.md` for screenshots and coverage.

| Command | Result |
|---|---|
| `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-m11d-accessibility-final-rerun2 -p no:cacheprovider` | PASS вЂ” 956 passed in 27.33s |
| `ruff check src tests` | PASS вЂ” all checks passed |
| `ruff format --check src tests` | PASS вЂ” 164 files already formatted |
| 
ode --check src/hf_tcm/studio/static/studio.js` | PASS |
| 
ode --check src/hf_tcm/studio/static/studio_ux.js` | PASS |

Read-only hash comparison matched all 694 M5вЂ“M10 output/config/non-evaluation
math fingerprints in `tmp/m11d-integrity-before.json`; no files were missing.
`docs/DEMO_RELEASE_MANIFEST.md` is unchanged. Scientific flags and ADR statuses
are preserved. No Monte Carlo, historical recomputation, or M12 work occurred.

## M11e final GUI patch and scientific baseline freeze вЂ” 2026-11-02

Fixed the Demo Studio's channel gain display to read `trace.input.channel_gain`
from the actual response schema, with a localized `РќРµРґРѕСЃС‚СѓРїРЅРѕ` fallback for
missing/null/non-finite values. Counts display as integers; rates, coefficients,
metrics, posterior values, and graph values retain round-trip-safe numeric
strings. Simple-mode labels are Ukrainian. A regression checks the displayed
gain and formatting after a real deterministic F=32 POST. The portability tests
keep immutable release-version metadata separate from demo configuration
invariants; no cross-environment mathematical reproduction is claimed.

Real Edge QA passed 293/293 checks and captured 36 screenshots at 1366Г—768 and
1920Г—1080. Both viewport runs made a deterministic F=32 POST. Gain, integer
counts, fallback handling, no `undefined`/`NaN`, Ukrainian Simple mode, all
four states/16 transitions, Inspector/help, 18 presentation steps, and file
downloads passed. There were zero console errors, network errors, or external
requests. Detailed output is in `tmp/m11e-browser-qa.json`.

| Command | Result |
|---|---|
| `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-m11e-final-rerun -p no:cacheprovider` | PASS вЂ” 958 passed in 25.13s |
| `ruff check src tests scripts` | PASS |
| `ruff format --check src tests scripts` | PASS вЂ” 166 files already formatted |
| `ruff check . --exclude 'chatgpt_review_bundle/**,tmp/**,.pytest*'` | PASS |
| `ruff format --check . --exclude 'chatgpt_review_bundle/**,tmp/**,.pytest*'` | PASS вЂ” 264 files already formatted |
| 
ode --check src/hf_tcm/studio/static/studio.js` | PASS |
| 
ode --check src/hf_tcm/studio/static/studio_ux.js` | PASS |
| 
ode --check scripts/qa_m11e_browser.js` | PASS |

Bare root Ruff traversal was also attempted; it encountered access-denied
warnings in old pytest basetemp paths and an unrelated F401 in the pre-existing
generated `chatgpt_review_bundle/build_bundle.py`; bare root format traversal
errored on that generated bundle. The project source/test/script scope and the
remaining repository source passed the scoped and excluded-root commands above.

Read-only M5вЂ“M10 fingerprint comparison matched **694/694** entries with zero
missing files or mismatches. `docs/DEMO_RELEASE_MANIFEST.md` and
`docs/M11D_SOURCE_FIDELITY_AUDIT.md` remain unchanged. Scientific source status
is `SOURCE_AUDIT_COMPLETE` / `PAPER_PARTIAL`; `paper_exact:false`,
`receiver_enabled:false`, and SCI-02/SCI-03/SCI-METRIC-02 OPEN remain. No
mathematics, historical data, Monte Carlo, or M12 work occurred. See
`M11E_FINAL_PATCH_REPORT.md` for the source note and detailed scope.

## M12a documentation-only verification

M12a created documentation and explanatory SVGs only. No production source,
GUI, accepted ADR, M5вЂ“M10 historical artifact, or immutable report was edited.
No receiver, estimator, decoder, Monte Carlo, pytest suite, Ruff, or Node QA was
run as part of M12a.

Read-only evidence checks inspected saved checkpoints and pooled integer counts
against frozen reports for M5f/M5h/M5j and M7/M8/M9/M10. The M7вЂ“M10 decoded-bit
checkpoint recounts matched their saved count records. M5j's post-evaluation
read-only recount remains the existing M5k audit; M5f/M5h checkpoint or frozen
counter totals were compared to their reports. No receiver outputs were
recomputed. Historical fingerprint comparison against
`tmp/m11d-integrity-before.json` matched **694/694**.

Documentation checks:

| Check | Result |
|---|---|
| `python -B -m py_compile docs/figures/generate_thesis_figures.py` | PASS |
| Parse all registered generated SVGs with `xml.etree.ElementTree` | PASS вЂ” 13/13 |
| Resolve all figure-register assets against the repository | PASS вЂ” 18/18 (13 SVGs and 5 pre-existing screenshots) |
| Thesis draft structure and word count | PASS вЂ” 57 Markdown headings; 5,298 words |
| Claim/evidence matrix rows | PASS вЂ” 32 claims |
| Table register rows | PASS вЂ” 17 tables |
| Historical fingerprints | PASS вЂ” 694/694 unchanged |

The read-only recount supports consistency of preserved outcomes, not a new
reproduction of stochastic results in another environment. Source fidelity
remains `PAPER_PARTIAL`; `paper_exact:false`, `receiver_enabled:false`, and
SCI-02/SCI-03/SCI-METRIC-02 remain open. M12b was not started.

## M11f вЂ” supervisor alignment and Signal Explorer

The read-only source audit compared Chapter 4 Code 2 (16 states, 64 table
transitions) with the separate four-state/16-edge article-v7/project model.
It recorded the Chapter 4 four-sample methodology entry and article-v7 eight
samples/symbol, plus article `О·=20`; current conditional Viterbi still runs the
complete frame. No source or receiver mathematics was changed. Existing
multipath, Rician, AWGN, and fluctuating-noise modules remain isolated from the
M11a trace path; integration requirements are listed in
`docs/M11F_CHANNEL_SIMULATION_GAP_ANALYSIS.md`.

Added a deterministic trace-backed Signal Explorer with a bounded 20-symbol Г—
8-sample visual window (160 samples for F=32), arbitrary integer sample offset,
symbol-step navigation, full-frame overview, 17 chart views, actual operands,
provenance, and synchronized TCM/Viterbi segment. The window is only a viewing
control; the decoder remains full-frame and no HMM channel posterior is shown.

ode --test tests/test_m11f_signal_window.js`: 5 passed. Node syntax checks
passed for `studio_ux.js`, `signal_window.js`, and
`scripts/qa_m11f_signal_explorer.js`. Real Edge F=32 explicit POST QA passed
68/68 checks at 1366Г—768 and 1920Г—1080, including all charts and first/middle/
last window indices; eight screenshots are saved in `docs/screenshots/`.

Final commands: `python -m pytest -q --basetemp tmp/pytest-m11f
-p no:cacheprovider` вЂ” **958 passed**; `ruff check src tests scripts` вЂ” PASS;
`ruff format --check src tests scripts` вЂ” PASS (166 files already formatted).
Read-only SHA-256 comparison with `tmp/m11d-integrity-before.json` matched
**694/694** M5вЂ“M10/studio math baseline entries. `paper_exact:false`,
`receiver_enabled:false`, `PAPER_PARTIAL`, and SCI-02/SCI-03/SCI-METRIC-02
OPEN remain. No Monte Carlo or new scientific performance evidence was run.
## M11g - interactive controls and projector UI

`python -m pytest -q --basetemp tmp/pytest-m11g-final-rerun -p no:cacheprovider` - **977 passed**. `ruff check src tests scripts` - PASS. `ruff format --check src tests scripts` - PASS (169 files already formatted). Node syntax checks passed for `studio_ux.js`, `signal_window.js`, and `qa_m11g_interactive_projector.js`; Node helper tests - **8 passed**. Real Edge QA - **106/106** at 1366x768 and 1920x1080, including explicit F=32 POST, input validation/file import, all 17 runtime charts, first/middle/last window synchronization, B preview, projector controls, and zero runtime exceptions. SHA-256 comparison to `tmp/m11d-integrity-before.json` - **694/694** preserved historical fingerprints. No Monte Carlo, receiver math, or M5-M10 artifacts were changed.

## M11h — supervisor source alignment and interactive demo acceptance

Source preflight hashes and presence checks are recorded in
`docs/M11H_SOURCE_VERSION_MATRIX.md`. The requested `references/supervisor/Раздел_4.doc`,
article-v7 DOCX, and RTF v2 are missing. The available Chapter 4 PDF, scanned
notes `4.pdf`, and older v3 DOCX were hashed; v3 was not treated as a
replacement for v7. A remains 4-state/16-edge; B remains a separate
source-derived 16-state/64-edge preview without phase interpretation or
receiver. `paper_exact:false`, `receiver_enabled:false`, and
SCI-02/SCI-03/SCI-METRIC-02 OPEN remain.

Projector views received presentation-only sizing for the trellis, estimator,
and decoder. B preview now displays the actual initial state, state ID path,
branch IDs, and source parameter B from its response; no math was changed.
Visual inspection still finds overlapping edge labels in the dense state-graph
view, so the projector demo verdict is PARTIAL.

Final verification:

- `python -m pytest -q --basetemp tmp/pytest-m11h-final -p no:cacheprovider` —
  **977 passed**.
- `ruff check . --exclude 'chatgpt_review_bundle/**,tmp/**,.pytest*,docs/figures/generate_thesis_figures.py'` — PASS.
- `ruff format --check . --exclude 'chatgpt_review_bundle/**,tmp/**,.pytest*,docs/figures/generate_thesis_figures.py'` — PASS, 292 files.
- Scoped checks `ruff check src tests scripts` and
  `ruff format --check src tests scripts` — PASS (169 files).
- Root Ruff traversal excluding only bundle/temp first found existing findings
  in `docs/figures/generate_thesis_figures.py` (M12a documentation generator);
  that file was unchanged and excluded in the passing root scan.
- Node syntax checks for `studio.js`, `studio_ux.js`, `signal_window.js`, and
  `scripts/qa_m11h_supervisor_acceptance.js` — PASS. Node helper tests —
  **8 passed**.
- Real Edge harness `scripts/qa_m11h_supervisor_acceptance.js` — **36/36** at
  1366×768 and 1920×1080. Includes changed-input deterministic F=32 POSTs, B
  preview from initial state ID 5 (trajectory 5→1→8→14), projector views,
  constellation, browser fullscreen, keyboard view navigation, and no runtime
  exceptions. Twelve screenshots are in `docs/screenshots/m11h-*.png`.
- Repeated `node scripts/qa_m11g_interactive_projector.js` on the final UI —
  **106/106**. First/middle/last windows (sample starts 0/48/96), synchronized
  trellis, all 17 charts, and 8/20/160/full-frame zoom passed on both viewports.
- Historical SHA-256 comparison to `tmp/m11d-integrity-before.json` —
  **694/694 matched**, no missing or changed entries.

No Monte Carlo, receiver mathematics, source documents, or M5-M10 artifacts
were changed. The Demo Studio JS/CSS edits are presentation and preview-display
only. M12 was not started.

## M11h-FINAL — source review and projector trellis (2026-11-04)

- `python -m pytest -q --basetemp tmp/pytest-m11h-final -p no:cacheprovider` — **977 passed**.
- `ruff check . --exclude 'chatgpt_review_bundle/**,tmp/**,.pytest*,docs/figures/generate_thesis_figures.py'` — PASS.
- `ruff format --check . --exclude 'chatgpt_review_bundle/**,tmp/**,.pytest*,docs/figures/generate_thesis_figures.py'` — PASS, 292 files.
- Node helper tests: signal-window 5/5, interactive controls 3/3, projector trellis 3/3; Node syntax checks for studio JS/CSS-adjacent scripts and both Edge harnesses — PASS.
- `node scripts/qa_m11h_supervisor_acceptance.js` — **50/50 checks total** across real Edge at 1366x768 and 1920x1080. Includes hidden-label computed style, A keyboard edge selection, A 4/16 and B 16/64 topology, detail/table modes, projector viewports, browser fullscreen, and deterministic input changes.
- `node scripts/qa_m11g_interactive_projector.js` — **106/106** across 1366x768 and 1920x1080; first/middle/last signal windows, sample/symbol alignment, trellis sync, 8-sample symbol zoom and 20-sample window.
- New Edge screenshots: `docs/screenshots/m11h-trellis-*.png`, `m11h-trellis-detail-*.png`, and `m11h-encoder-b-trellis-*.png`, plus the remaining `m11h-*.png` views.
- Historical SHA-256 recount against `tmp/m11d-integrity-before.json`: **694/694 matched**, zero missing/changed.
- Source alignment remains incomplete because the requested supervisor chapter DOC, article v7 DOCX, and translation RTF are absent. Encoder B stays preview-only. `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN.
- No production receiver mathematics, M5-M10 artifacts, supervisor source documents, or historical results changed. No Monte Carlo or M12 was run.


## M11j - Minimalist Simulation Studio UX (2026-11-06)

- `python -m pytest -q` - PASS, **977 passed in 77.19s**. Pytest emitted a post-success Windows ACL cleanup warning for the existing protected `%TEMP%/pytest-current`; exit status was 0.
- `ruff check src tests scripts` - PASS. `ruff format --check src tests scripts` - PASS, 169 files already formatted.
- Node syntax: `studio_ux.js`, `minimalist_state.js`, `qa_m11j_minimalist_studio.js` - PASS.
- Node helpers: M11j 5/5, M11g controls 3/3, M11f window 5/5, M11h trellis 3/3 - PASS when run individually. Combined `node --test` was not counted because sandbox process spawning returned `EPERM`.
- Real Edge `node scripts/qa_m11j_minimalist_studio.js` - **50/50**, at 1366x768 and 1920x1080. Real Edge `node scripts/qa_m11g_interactive_projector.js` - **106/106** at both viewports.
- M11j screenshots: 12 files under `docs/screenshots/m11j-*.png`.
- Historical hash recount against `tmp/m11d-integrity-before.json`: **694/694 matched**, zero missing/changed.
- Verification and UI limits: `docs/M11J_MINIMALIST_UX_REPORT.md`, `docs/M11J_BROWSER_QA_REPORT.md`.
- `paper_exact:false`; `receiver_enabled:false`; SCI-02/SCI-03/SCI-METRIC-02 OPEN. Encoder B remains preview-only. No Monte Carlo, receiver mathematics, ADRs, M5-M10 artifacts, or M12 were changed/run.

## REPRO-02 — Scientific transmitter (2026-11-06)

- `python -m pytest tests/repro -q --tb=short -p no:cacheprovider -p no:tmpdir` — **23 passed**.
- `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro02-final -p no:cacheprovider` — **1000 passed in 31.83s**.
- `ruff check src tests` — PASS. `ruff format --check src tests` — PASS, **182 files already formatted**.
- `python -m hf_tcm.repro.transmitter --config configs/repro02/n_star_transmitter_only.json --output outputs/repro02/reference_n_star --print-summary` — transmitter-only reference succeeded. 20,000 TCM steps, 40,000 input bits, 60,000 coded bits, 160,000 complex ZOH samples; no channel/receiver/BER/SER.
- Output validation: 20/20 NumPy array SHA-256 values matched manifest; 10 SVGs parsed as valid XML; repeated deterministic run produced identical arrays and summary.
- Historical M5-M10 fingerprints compared with `tmp/m11d-integrity-before.json`: **694/694 matched**, 0 missing, 0 changed.
- Independent oracle checked all 16 Encoder A state/input combinations. The earlier REPRO-01 vectors were corrected where they conflicted with their own recurrence equations; details in `docs/repro/REPRO_02_ENCODER_VERIFICATION.md`.
- Python files changed only in new `src/hf_tcm/repro/` namespace and `tests/repro/`; no Node/GUI files changed, so Node checks were not applicable. ACL-protected pytest temporary paths were not removed.
- `paper_exact:false`; `receiver_enabled:false`; SCI-02/SCI-03/SCI-METRIC-02 OPEN. REPRO-03 not started.

## REPRO-03 — physical-channel project reconstruction (2026-11-06)

- `python -m pytest tests/repro/test_channel.py tests/repro/test_channel_io_and_plots.py -q --tb=short --maxfail=1 -p no:cacheprovider -p no:tmpdir` — **21 passed in 2.22s**.
- `python -m pytest tests/repro -q --tb=short --maxfail=1 -p no:cacheprovider -p no:tmpdir` — **44 passed**.
- `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro03-final -p no:cacheprovider` — **1021 passed in 71.53s**.
- `ruff check src tests` — PASS. `ruff format --check src tests` — PASS, **194 files already formatted**.
- CLI validated all three profiles. Channel-only multipath run consumed `outputs/repro02/reference_n_star`: 160,000 transmitter samples became 160,003 received samples for delays 0 and 3; two Rician AR(1) paths plus independent sample-domain AWGN; no receiver/BER/SER.
- Single-run timings: channel 0.1498s; 16 SVG plots 0.0980s. Materialized channel arrays 27,240,456 bytes; output tree 18,323,384 bytes. These are one run, not a benchmark; process peak RSS was not measured.
- Deterministic validations: identity equality, complex multiplication, pure delay/tail, independent two-path fixture, zero noise, separated seeds; AWGN N=300,000 gave I/Q means -0.001226/-0.000302 and variances 0.199798/0.199504 for expected 0.2. Rician N=250,000 gave total power 0.751774, diffuse 0.187925 (expected 0.1875), lag-1 correlation 0.720323+0.001519j (configured 0.72).
- Channel manifest hashes and all 16 SVG hashes verified; SVG XML parsed. Observation hash `1bc276f254e358b5a4a52e8585f9a5616d00f554e3a84847a26cd58f16cb34ed`; receiver NPZ `1d9c1c95e0dcfb80971b000a2fc392697931f8cde38fee56990ea966fb6260e4`; truth NPZ `fe9db789be9c27023bd60e564bcc7e0afdd1eaab09cf8f078c540afe2e027b2c`; manifest `0f291e155dd586901aafd94df3b374208c0b7c04b097c35f44d046fc40d33ae2`. Provenance includes REPRO-02 transmitter sample and information-bit hashes.
- Historical SHA comparison against `tmp/m11d-integrity-before.json`: **694/694 matched**, zero missing/changed. Source `references/source_paper_2026.docx` hash unchanged. Corrected REPRO-01 vector/spec hashes are recorded in `docs/repro/REPRO_03_FINAL_REPORT.md`.
- Existing M5-M11 channel/receiver modules, REPRO-02 transmitter math, historical artifacts, and GUI were not changed. Correlated A(9)-(10) quadrature-noise conversion, fractional delays, physical Eb/N0, RF/passband, Jakes/Doppler and receivers remain outside this implemented profile. `paper_exact:false`, `receiver_enabled:false`; REPRO-04 not started.

## REPRO-04 — separate hard 8PSK / Hamming Viterbi receiver (2026-11-06)

- Focused tests: `python -m pytest -q tests/repro/test_separate_receiver.py --tb=short --basetemp tmp/repro04-focused-last -p no:cacheprovider` — **16 passed**.
- Full regression: `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro04-final -p no:cacheprovider` — **1037 passed in 33.35s**.
- `ruff check src tests` — PASS. `ruff format --check src tests` — PASS, **205 files already formatted**.
- `python -m hf_tcm.repro.receiver_cli --config configs/repro04/reference_n_star_receiver.json --input outputs/repro03/reference_n_star --output outputs/repro04/reference_n_star --print-summary` — PASS. Processed 20,000 symbols from the public 160,003-sample observation; sample indices 160000–160002 remain explicitly unused. No `evaluation_truth.npz` was loaded. Receiver path metric 4247 is a run-specific diagnostic only.
- One transmitter-independent identity fixture recovered all payload bits with zero bit/symbol errors under explicit zero-tail and matching nominal constellation. Tests cover eight 8PSK points, reconstructed inverse-label bijection, all sixteen edges, integer Hamming costs, deterministic ties, nonzero initial state, static known gain, single-path noisy repeatability, multipath tail alignment, public input and receiver-output serialization round trips, plot generation, and truth isolation.
- Reference input SHA-256 `1bc276f254e358b5a4a52e8585f9a5616d00f554e3a84847a26cd58f16cb34ed`; NPZ output SHA-256 `8682e31a56c60d11c7c9e9b9530392ba5af59cf55a076f901ce245ef64e283aa`; output-array hash `683052c7d5ee6bd4ed8eaa63f62395e6a706ece57ef93716c22d490eb8f789ad`. Ten SVGs and performance records are under `outputs/repro04/reference_n_star/`; manifest hashes cover result, plots and performance JSON.
- One measured run: receiver 0.3141s (demodulation 0.0093s; Hamming matrix 0.0118s; Viterbi 0.2555s), plot writing 0.0312s; materialized receiver arrays 4,240,058 bytes; compressed result NPZ 1,572,548 bytes. Single run only; peak RSS not measured.
- Historical baseline recount against `tmp/m11d-integrity-before.json`: **694/694 matched**, no missing/changed files. No M5-M11, REPRO-02/03 source/math or historical artifact changes; no Monte Carlo or REPRO-05.
- `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN. ADR-002 phase mapping is reconstructed. Front end does not equalize unknown time-varying Rician multipath. Full-frame traceback is not `eta=20`.

## REPRO-05 — joint Euclidean demodulation/decoding (2026-11-06)

- Focused REPRO-05: `python -m pytest -q tests/repro/test_joint_receiver.py --tb=short --basetemp "%TEMP%\hf-tcm-repro05-target-final-3" -p no:cacheprovider` — **18 passed**. The Windows user temp location avoided pytest cleanup's OneDrive ACL denial.
- Final full regression: `python -m pytest -q --tb=short --maxfail=1 --basetemp "%TEMP%\hf-tcm-repro05-full-release" -p no:cacheprovider` — **1055 passed in 70.99 s**.
- `ruff check src tests` — PASS. `ruff format --check src tests` — PASS, **216 files already formatted**. No JS/GUI files changed; Node/Edge checks were not applicable.
- Same-observation integration: REPRO-04 and REPRO-05 consumed observation SHA-256 `74697c52e4537bf899e1143f1b2c7111d0d121505566c94d6a0bb097936bd722`; both recovered all 40,000 bits on the same noiseless identity reference (zero bit/symbol errors). Descriptive fixture only, not statistical evidence.
- Paired CLI: joint config `configs/repro05/reference_n_star_joint.json`, separate config `configs/repro04/reference_n_star_receiver.json`, same receiver-only input under `outputs/repro05/reference_n_star/observation`. It saved a paired REPRO-04 bundle and comparison plot. REPRO-05 processed all 20,000 symbols / 160,000 samples and recorded 26 arrays, including candidate predictions `(20000,16,8)`, per-candidate estimator values `(20000,16)`, all 160,000 sample indices, and no unused samples. Fourteen actual-data SVGs parsed and matched their hashes. Traceback is full-frame, not eta=20.
- Observation SHA-256 `74697c52e4537bf899e1143f1b2c7111d0d121505566c94d6a0bb097936bd722`; config SHA-256 `522b0922a18a0c0230868d778da47a74081f71c5bf1e1b927730c915da8cb462`; result-array SHA-256 `b4ee1d8182f06dc05d09d436ec438f7453811d535b24edd8bff236e05368cf52`; NPZ SHA-256 `bd636e1a29a210ddda700e242aa0bb006d5fe4ea654e8e429fad23b1d0a76bea`; final manifest SHA-256 `e8f84f6970fea42187471440dd1a56715c5a8409c763bb9ff09bd9cd76a7cbb8`.
- One-run timings: receiver 1.621 s (candidate generation 0.038 s; metrics 0.535 s; posterior/estimator 0.760 s; Viterbi 0.178 s), plots 3.995 s; arrays 55,360,482 bytes; paired output tree 18,113,934 bytes. Not a benchmark. F=256 identity and F=32 seeded adaptive single-path Rician tests passed.
- Historical recount against `tmp/m11d-integrity-before.json`: **694/694 matched**, zero changed/missing. Identity and public static gain supported; single-path Rician runs without truth and has no accuracy guarantee. Multipath is explicitly rejected as `MULTIPATH_JOINT_RECEIVER_PARTIAL`. A(1) complex update, pseudo-prior, and A(2) squared residual remain project reconstructions; ADR-002 remains reconstructed. `paper_exact:false`, `receiver_enabled:false`; SCI-02/SCI-03/SCI-METRIC-02 OPEN. No Monte Carlo, REPRO-06, GUI, REPRO-04 math, or M5-M10 artifact changes.

## REPRO-06 — finite-depth Viterbi η=20 (2026-11-06)

- Focused core and both receiver tests: **63 passed**; separate finite zero-tail contract tests: **2 passed**.
- `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro06-final -p no:cacheprovider` — **1086 passed in 34.26s**. A new workspace-local basetemp required elevated access because the sandbox's pytest temp inspection encountered the documented Windows ACL error; no protected directory was removed.
- `ruff check src tests` — PASS. `ruff format --check src tests` — PASS, **219 files already formatted**. `python -m compileall -q src/hf_tcm/repro` — PASS.
- `python -m hf_tcm.repro.receiver_cli ... --validate-only --traceback-depth 20` and `python -m hf_tcm.repro.joint_receiver_cli ... --validate-only --traceback-depth 20` — both accepted the stored configs and same observation without running a receiver.
- Shared engine `FiniteDepthViterbiDecoder` accepts one 16-edge Hamming integer or Euclidean float row, emits regular decisions after η rows, uses a ring capped at η predecessor rows, and flushes all remaining symbols with actual tail depth. Existing full-frame defaults and metric/estimator stages are unchanged. Zero-tail tests verify the declared public terminal state and payload trimming.
- Existing identity observation SHA-256 `74697c52e4537bf899e1143f1b2c7111d0d121505566c94d6a0bb097936bd722`: 20,000 symbols / 160,000 samples. Both article-oriented compact finite receivers consumed this exact observation, returned 40,000 payload bits, and had 0 errors in this noiseless fixture only. Each ring was capped at 20 rows and survivor diagnostic matrices were `(0,4)`. Separate arrays hash `814ff1a084a611539e56f415a7951755ae4ab1a323bd9aa0928438b9e963674d`; joint result hash `99fbb0eec5b1625af00483c9dfeb86bd7f860eb4cdb5cc85b0d9ff91874fe19f`.
- A deterministic 256-symbol metric-only fixture shows η=20's first decision at symbol 0 / availability 19 and a path difference at symbol 68 versus full-frame. Its actual-data comparison plot is `outputs/repro06/full_vs_eta20_fixture/full_vs_eta20.svg`, SHA-256 `254be29eb4dfd419955f30d86f70d617f5c46b0756dee36d848112f171db6158`. It is not BER or channel evidence.
- One-run measurements on existing 32/256/20,000-symbol Hamming and joint metric rows are in `docs/repro/REPRO_06_PERFORMANCE.md` and `outputs/repro06/performance.json`; at 20,000 symbols the η=20 ring stayed at 20 rows versus full-frame's 20,000. Process RSS was unavailable; timings are single observations, not benchmarks. Output manifest SHA-256 `3b5119a43024e261121e8a0ae8f59b0f5e51a2b10102b0cbcbb9131efb6f8ead`; all **11/11** listed files verified.
- Historical comparison with `tmp/m11d-integrity-before.json`: **694/694 matched**, no missing/changed artifacts. `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN; `MULTIPATH_JOINT_RECEIVER_PARTIAL` remains. No Monte Carlo, GUI change, or REPRO-07.

## REPRO-06B — static-known ISI-aware joint MLSE (2026-11-07)

- Focused ISI-aware suite: `python -m pytest -q tests/repro/test_augmented_trellis.py tests/repro/test_isi_predictor.py tests/repro/test_isi_metrics.py tests/repro/test_expanded_viterbi.py tests/repro/test_multipath_joint_receiver.py tests/repro/test_multipath_evaluation.py --tb=short --maxfail=1 --basetemp tmp/pytest-repro06b-focused-final -p no:cacheprovider` — **35 passed in 3.22 s**.
- Final full regression after output serialization changes: `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro06b-final -p no:cacheprovider` — **1121 passed in 70.21 s** (fresh workspace-local basetemp; no ACL-protected folder was deleted). Unprivileged pytest setup/cleanup had encountered the previously documented Windows ACL error; the final runs used the required workspace access.
- `ruff check src tests scripts` — PASS. `ruff format --check src tests scripts` — PASS, **238 files already formatted**.
- `python scripts/run_repro06b_reference.py` — one deterministic pipeline each for F=32, F=256, and F=20,000. It uses project-defined static gains `h0=1+0j`, `h1=0.35+0.15j`, delays `[0,3]`, no noise; values are not attributed to the article. For F=20,000: 40,000 input bits, 160,000 Tx samples, 160,003 Rx samples; D=3 tail indices 160000–160002 are scored in transition 19999. Joint and Hamming arms consumed the same observation hash `8a1a86fd4cc6362e5b100ae3a1c157b122085da51b8bcbed0df2a266057cb958`. Both returned zero errors in this single noiseless fixture; no performance or superiority claim.
- Reachable trellis: D=0: 4/16; D=3: **17 states / 68 edges**; D=9 and D=16: 69/276. Reference configuration runs finite-depth eta=20; survivor ring maximum is 20 rows. Independent F=4 exhaustive search across 256 input sequences agrees with full-frame Viterbi sequence and cost.
- One F=20,000 timing observation: channel 0.0288 s; joint receiver 1.1245 s (metric matrix 0.2193 s, Viterbi 0.8241 s); separate Hamming 0.6584 s; plots 0.1648 s. Compressed observation/joint/separate arrays: 326,334 / 1,329,660 / 474,055 bytes; SVGs total 4,435,200 bytes. Single run only; peak RSS not measured.
- `python scripts/verify_repro06b_artifacts.py` — 76/76 REPRO-06B run files SHA/size verified; 27 SVGs parsed as XML; historical M5–M10 fingerprints **694/694 matched**, no missing/changed files. Root manifest SHA-256 `da2bf0f4ac1c065ee5e59104e5fc3eb62f9b699e28122884b96d8735819aa316`.
- `python -m hf_tcm.repro.multipath_receiver_cli --config configs/repro06b/receiver_static_2path_eta20.json --input outputs/repro06b/reference_static_2path/F20000/channel --separate-config configs/repro06b/separate_hamming_eta20.json --validate-only` — PASS; no receiver was run by this validation-only command.
- Adaptive unknown Rician multipath is deliberately unavailable pending survivor-specific causal estimation. Therefore overall `REPRO_06B_MULTIPATH_PARTIAL`; static-known MLSE, augmented trellis, eta=20 integration and truth isolation are ready. `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN. No GUI, Node/Edge QA, Monte Carlo, REPRO-07, or historical receiver/math changes.


## REPRO-09 — scientific GUI (2026-11-09)

- Existing studio extended; command `python -m hf_tcm.demo_studio --view scientific`. Real Edge CDP QA passed at 1366×768 and 1920×1080, including no run on page load, real Identity simulation, paired observation hash, trace view, and one actual paired REPRO-07 trial. Screenshots: `docs/screenshots/repro09-scientific-identity-1366x768.png`, `docs/screenshots/repro09-scientific-workspace-1920x1080.png`.
- Targeted GUI/backend tests: `python -m pytest tests/repro/test_scientific_workspace.py -q --tb=short -p no:cacheprovider -p no:tmpdir` — 6 passed. Browser smoke was one paired trial only; its confidence interval correctly reports too few independent trials, so this is functionality evidence, not scientific comparison evidence.
- Scoped `ruff check` and `ruff format --check` on changed Python files — PASS. `node --check` for scientific UI, i18n, and Edge QA driver — PASS.
- First full pytest attempt exposed a route regression (`POST /api/demo` returned no response). Route was traced and restored; the isolated old endpoint test then passed. Final full suite after the correction: `python -m pytest -q --tb=short --maxfail=1 -p no:cacheprovider` — **1167 passed in 54.75 s**.
- Historical verifier `python scripts/verify_repro06b_artifacts.py`: 76/76 REPRO-06B files verified; 693/694 historical fingerprints matched. The only changed historical-list entry is `src/hf_tcm/demo_studio.py`, extended to add the explicitly selected scientific launch mode while retaining old default launch. No M5–M10 result files were edited. Do not report 694/694 unchanged.
- `REPRO_09_SCIENTIFIC_GUI_PARTIAL`; missing acceptance includes complete selected-edge/Viterbi path inspection, dedicated 20-sample zoom, B1/legacy experiment browsing, long-frame and multi-trial MC browser acceptance. `paper_exact:false`; no REPRO-10.


## REPRO-06C - survivor-specific adaptive multipath joint receiver (2026-11-09)

- Targeted REPRO-06C estimator/config/receiver suite: 14 passed. Final full regression rerun: `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro06c-final4 -p no:cacheprovider` — **1135 passed in 34.49 s**. The sandbox required elevated workspace access for pytest because the Windows pytest temp root has ACL-protected entries; no protected directories were removed.
- ruff check src tests scripts/run_repro06c_paired_checks.py scripts/run_repro06c_reference_frame.py - PASS. The corresponding ruff format --check - PASS, 246 files already formatted. No GUI changed, so Node/Edge checks did not apply.
- Paired F=32 controls used one shared ReceiverObservation SHA in both arms. Identity: both 0/64 bit errors. Existing REPRO-06B known-static two-path MLSE: 0/64; separate Hamming: 0/64. Adaptive unknown-static with explicit nominal prior, slow Rician AR(1) rho=0.995, and Rician AR(1)+AWGN rho=0.85: each 0/64 in this fixed fixture. Hamming paired results: 0/64, 4/64 and 8/64 respectively. Descriptive single frames only, not statistical claims.
- F=256 seeded two-path Rician AR(1)+AWGN: Tx=2048 samples, Rx=2051; eta=20 ring maximum 20; adaptive output 512 bits with 6 errors (evaluation only). Adaptive receiver time 2.01 s (single run), NPZ SHA-256 bc5ef274a6476aaa2cfa598c67b2336b174b8a90539b3f99709d799cb61da944.
- REPRO-03 20,000-symbol Rician AR(1) observation: 160,000 Tx / 160,003 Rx samples; 40,000 decoded bits; D=3 tail scored in final TCM step; 17 states / 68 transitions; eta=20 survivor ring max 20. Receiver time 152.96 s; NPZ size 28,031,692 bytes; result SHA-256 e651e1f636717c985b45d38be8f3f4a206026dd235919bca90820afcd46985ac; NPZ SHA-256 2f06ba4ee9cb887440a75ff47a75c541047a54f9d66e93eeca1f3ded699ea3ef. One measurement only, not a benchmark.
- verify_adaptive_result verified six output manifests (F=20,000, F=256 and four F=32 adaptive arms); 72 REPRO-06C SVGs parsed as XML. Historical checker: 76/76 REPRO-06B files and 694/694 M5-M10 fingerprints verified.
- Root `ruff check .` is blocked by ACL-denied traversal and 27 existing findings in generated `docs/figures/generate_thesis_figures.py`; root `ruff format --check .` fails on traversal with `Expected a ruff source file`. Scoped Ruff check/format for source, tests and REPRO-06C scripts pass. No generated thesis artifact was changed.
- Receiver accepts only ReceiverObservation; EvaluationTruth is excluded. Unknown-static is h[n] constant with explicit public prior; Rician profiles use sample-level h prediction/update with public LOS mean, K/power/rho. Survivor-specific processing is an approximation with one filter per winning expanded node, not global joint ML. No Monte Carlo; paper_exact:false, receiver_enabled:false; REPRO-07 not started.

## REPRO-07 paired BER/SER experiment (2026-11-09)

- Added isolated paired runner, domain-separated bits/fading/noise seeds, common observations, ratio-of-sums BER/SER, paired cluster bootstrap, hash-verified resume, resource limits, CLI, measured SVGs, and guarded energy-gain preparation. Outputs are under outputs/repro07/.
- Deterministic F=32 identity and public known-static two-path controls completed without errors in both receiver arms. Main pilot pilot_rician_ar1_f256_v1 completed 60/60 paired F=256 trials: 20 at each complex sample-domain noise variance 0.005, 0.05, 0.2; 512 information bits/frame; eta=20; delays [0,3]; path powers [1,0.25]; K [4,1]; LOS phases [0,0.7] rad; sample AR(1) rho=0.98. BER Joint/Separate: 0.000390625/0.14501953125, 0.0005859375/0.14609375, 0.0017578125/0.1455078125. DeltaBER: -0.14462890625, -0.1455078125, -0.14375. Paired 95% cluster CIs: [-0.15869140625,-0.13007568359375], [-0.165234375,-0.12626953125], [-0.1583984375,-0.12900390625]. Results compare two complete algorithms and this project profile; they are not metric-only or paper-exact evidence, and noise variance is not Eb/N0.
- One F=20,000 resource-check pair completed at variance 0.05: Joint 16/40,000, Separate 6,019/40,000; one pair provides no statistical inference. Single observed receiver times were 238.66 s and 0.649 s, not a benchmark. Resume was verified on pilot and long-frame runs.
- REPRO-07 focused tests: 18 passed. Full pytest: 1153 passed. Scoped Ruff check/format passed. Root-wide Ruff check encountered ACL-denied traversal and 27 existing findings in generated docs/figures/generate_thesis_figures.py; root-wide format traversal failed with Expected a ruff source file. Historical verifier: 76/76 bundle files and 694/694 M5-M10 fingerprints matched. All four REPRO-07 experiment roots passed verify_experiment; GUI unchanged.
- No REPRO-02 through REPRO-06C mathematics, M5-M10 output, GUI, or accepted ADR changed. paper_exact:false; receiver_enabled:false. REPRO-08 was not started.


## REPRO-08 - bounded article-reproduction investigation (2026-11-09)

- Added B1 static-public-tap hard 8PSK/Hamming front end in `src/hf_tcm/repro/repro08_channel_aware_hard.py` and a discrete ZOH energy convention in `repro08_energy.py`; no existing REPRO-04/05/06C receiver math was changed. Targeted tests: `python -m pytest -q tests/repro/test_repro08_channel_aware_hard.py tests/repro/test_repro08_energy_normalization.py --tb=short --maxfail=1 --basetemp "$env:TEMP\hf-tcm-repro08-final-target" -p no:cacheprovider` - **8 passed**.
- Full regression: `python -m pytest -q --tb=short --maxfail=1 --basetemp "$env:TEMP\hf-tcm-repro08-full" -p no:cacheprovider` - **1160 passed in 94.14 s** before adding one final independent hand-calculated delay-3 test. Final full-suite rerun after the independent hand-calculated delay-3 test: `python -m pytest -q --tb=short --maxfail=1 --basetemp "$env:TEMP\hf-tcm-repro08-final-full" -p no:cacheprovider` - **1161 passed in 90.86 s**.
- Scoped lint: `ruff check src/hf_tcm/repro tests/repro` and `ruff format --check src/hf_tcm/repro tests/repro` - PASS, 87 files formatted.
- REPRO-07 Rician pilot read-only audit: 60/60 existing pairs, 20 per variance 0.005/0.05/0.2, same receiver observation hashes. B0 BER 0.1450195/0.1460938/0.1455078 and phase SER 0.2896484/0.2994141/0.2951172. Existing results were not changed.
- New Phase A: 10 F=64 controls. New Phase B: 120 completed F=256 paired trials (two explicitly separated 3-point static-known-CSI pilots; 20 trials/point, three receiver arms, paired hashes verified). New Phase C: one F=20,000 Rician AR(1) pair completed in 147.804 s under a 300 s budget; 40,000 bits, Joint 21 errors, B0 5,828 errors. This is a bounded resource check, not a long-frame statistical series.
- Actual BER, information-pair SER, phase-symbol SER, paired cluster-bootstrap intervals, and nine plots (including three selected diagnostic SVGs copied read-only from REPRO-07) are under `outputs/repro08/`. A further 60 REPRO-06C adaptive static-prior receiver calls replayed the exact 60 v2 observations; all 60 observation hashes matched B1. Their post-processing wall time was not captured, so it is not reported as a benchmark.
- Final REPRO-08 root manifest SHA-256: `070c395e6e8a664f69770def223ca2d8306ebbcbdafb9444adf7471954bf36ac`; **23/23** payload entries verified. `python scripts/verify_repro06b_artifacts.py` - PASS: historical M5-M10 fingerprints **694/694 matched**, no missing/changed files.
- `python scripts/verify_repro06b_artifacts.py` - PASS: 76/76 files, 27 SVG XML parses, historical M5-M10 fingerprints **694/694 matched**.
- Article exact v7 file and chapter DOC were absent. The discrete `gamma_b,d` axis is not physical Eb/N0; energy gain is not estimable, p*=0.05 is not assumed to be decoded payload BER, and the historical 1.5 dB claim is not confirmed. `paper_exact:false` remains. REPRO-08 is PARTIAL; no REPRO-09, GUI, or Monte Carlo beyond the bounded paired pilots was started.
## REPRO-09B — Scientific Workspace completion (2026-11-10)

- Launch command verified with automatic browser open: `python -m hf_tcm.repro.scientific_studio --port 18769`. HTTP checks confirmed both `/` and `/scientific` return the Scientific Workspace, not M11.
- `node scripts/qa_repro09b_scientific.js` — PASS. Real Edge flows covered scientific launcher root `/` (not legacy M11), Identity + B1 and save/load; synchronized selected symbol; Encoder A 4/16 trellis; chosen survivor endpoint and edge; η=20 source/arrival timing; separate 20-sample zoom; static `[0,3]` 17/68 trellis + B1; Rician with B1 disabled; MC stop at pair boundary and resume to 10/10 pairs over two noise levels; verified lazy F=20,000 archive. Viewports: 1366×768 and 1920×1080. Screenshots: `docs/screenshots/repro09b-viterbi-1366x768.png`, `docs/screenshots/repro09b-long-frame-1920x1080.png`.
- `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro09b-final-fix -p no:cacheprovider` — **1174 passed in 60.25 s**, including HTTP root routing for the Scientific Workspace launcher.
- `ruff check src/hf_tcm/studio/scientific.py src/hf_tcm/studio/server.py src/hf_tcm/repro/scientific_studio.py src/hf_tcm/demo_studio.py tests/repro/test_scientific_workspace_09b.py` — PASS. Same paths with `ruff format --check` — PASS (5 files formatted).
- `node --check src/hf_tcm/studio/static/scientific.js`, `node --check src/hf_tcm/studio/static/scientific_i18n.js`, `node --check scripts/qa_repro09b_scientific.js` — PASS.
- Reopened and verified three single-run manifests; completed REPRO-07 pilot manifest (12 files); REPRO-08/06C long-frame manifests. F=20,000 metrics and the archived decoder trace intentionally remain separate because their observation hashes differ; no long simulation was launched for viewer QA.
- Historical check `python scripts/verify_repro06b_artifacts.py`: 76/76 REPRO-06B files and 27 SVGs valid, historical fingerprints **693/694**. Sole mismatch remains `src/hf_tcm/demo_studio.py`; the expected original bytes were unavailable, and neither fingerprint expectations nor checker were changed. Do not report 694/694.
- Overall: `REPRO_09B_SCIENTIFIC_GUI_PARTIAL`; GUI behavior listed above is verified. `paper_exact:false`; no REPRO-10 started. The full root-wide Ruff traversal was not run; ACL-protected paths remain untouched.

## REPRO-10 — final application acceptance (2026-11-10)

- Windows Scientific Workspace launch command verified: `python -m hf_tcm.repro.scientific_studio --port 18769 --no-browser`; `/`, `/scientific`, and `/api/health` responded as expected.
- Edge QA via `node scripts/qa_repro09b_scientific.js`: Identity, static multipath, Rician, trellis/survivor/η=20, sample zoom, save/load, 2-level/5-trial paired Monte Carlo stop/resume, long archive viewer, and real PNG download. Viewports 1366×768 and 1920×1080. Screenshots and actual PNG listed in `docs/repro/REPRO_10_FINAL_ACCEPTANCE_REPORT.md`.
- Historical archive recovery: original `src/hf_tcm/demo_studio.py` restored from `chatgpt_review_bundle/02_PYTHON_SOURCE_AND_GUI.zip`; SHA-256 `2f652479da237220358a1e0343cc4cbe591d0d88ea4ededfb4bb47b30acff815`. `python scripts/verify_repro06b_artifacts.py` — 694/694 historical fingerprints, 76/76 REPRO-06B files, 27 SVGs valid.
- Scoped Ruff check/format and Node syntax checks passed. `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro10-final -p no:cacheprovider` — **1174 passed in 153.40 s**.
- Scientific restrictions remain: `paper_exact:false`; `ARTICLE_REPRODUCTION_INSUFFICIENT_DATA`; `ENERGY_GAIN_NOT_ESTIMABLE`; no physical Eb/N0 or 1.5 dB claim. Root-wide Ruff and clean-machine Windows installation were not claimed. ACL-protected temp paths were left untouched.

## REPRO-10A — BER/SER and graph-export hotfix (2026-11-10)

- BER audit identified a metric-label mismatch: archived `separate.ser` counted pre-Viterbi hard 8PSK phase errors, not decoded information-pair errors. Read-only recount from saved NPZ arrays: F=256 = 56/512 bit errors, 47/256 information-pair errors (SER 0.18359375), 60/256 phase errors (SER 0.234375); F=32 = 7/64 bit errors, 6/32 pair errors (SER 0.1875), 9/32 phase errors (SER 0.28125). The paired-bit invariant holds. Old summary/trace SHA-256 values were unchanged. Evidence: `docs/repro/REPRO_10A_BER_SER_AUDIT.md`, `outputs/repro10a/audit/legacy_pair_ser_recount.json`.
- Added explicit `information_pair_*` and `phase_symbol_*` summary fields; retained legacy aliases for compatibility. Old summaries with decoder traces are enriched in memory only. Eight targeted tests cover independent count fixtures, validation, same-run integration and old-file immutability.
- The transparent PNG defect was an asynchronous rendering race: controls enabled from summary state before `drawAll()`. Export now waits for per-canvas rendering and opaque white background; Viterbi has actual trace-backed SVG export. Edge decoded each PNG and verified opacity/non-empty content. Tx/Rx/metric/error PNGs: 800×300; Monte Carlo BER: 581×250; all opaque. SVG parsed with 90 trellis paths. HTTP HTML/JS/JSON charset and Edge UTF-8 button label checked.
- Real Edge QA `node scripts/qa_repro09b_scientific.js` with `REPRO09_URL=http://127.0.0.1:18770`: **19/19 checks passed**. Included Identity/B1, static multipath `[0,3]` with 17/68 trellis/B1, Rician/B1 gating, selected survivor/η=20, save/reload, two noise levels × five Monte Carlo trials, stop/resume to 10/10, graph exports and F=20000 lazy archive viewer. Viewports 1366×768 and 1920×1080. Screenshots: `docs/screenshots/repro10a-*`; report: `outputs/repro10a/acceptance/gui_qa_report.json`.
- New F=32 controls in `outputs/repro10a/reference_runs/`: identity; static multipath `[0,3]`; and Rician AR(1). They preserve the actual traces, decoded bits, summaries and manifests. Paired GUI experiment is copied read-only and verified at `outputs/repro10a/paired_experiment/`.
- `python scripts/verify_repro10a_outputs.py` — PASS: three single-run manifests, 12 paired-experiment files, seven plot exports and ten screenshots. Full content hashes and visual checks: `outputs/repro10a/audit/output_integrity.json`.
- Full regression: `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro10a-final-20261110 -p no:cacheprovider` — **1182 passed in 58.14 s**. `ruff check src tests` — PASS. `ruff format --check src tests` — PASS, 261 files. Scoped Ruff on changed Python source/tests/scripts — PASS. `node --check src/hf_tcm/studio/static/scientific.js` and `node --check scripts/qa_repro09b_scientific.js` — PASS.
- `python scripts/verify_repro06b_artifacts.py` — 76/76 REPRO-06B files, 27 SVGs valid, historical M5–M10 fingerprints **694/694**, zero failures. Receiver/transmitter/channel mathematics were not changed. `paper_exact:false`, `ENERGY_GAIN_NOT_ESTIMABLE`; no 1.5 dB reproduction claim. ACL-protected temp/cache directories were not removed. The archive is at project root as `HF_TCM_SIM_REPRO_10A_AUDIT.zip`.

## GUI-UX-02 verification

1182 pytest passed; src/tests Ruff check and format passed; Node syntax passed; historical verifier 694/694, 76/76 payload. Five F32 backend controls and 10 independent paired trials completed; deterministic resume completed without duplicate records. Edge passed 12 checks including all five profiles, four I/Q toggles, fixed constellation geometry and GUI Monte Carlo 10/10; 22 screenshots cover both requested viewport sizes. Four PNG/SVG exports decoded/parsed and checked for visible content. The final BER-toggle/color patch has syntax checks but repeated browser acceptance stalled, so GUI status remains PARTIAL. Full logs: outputs/gui_ux_02/logs/.

## GUI-ENERGY-01

- Final full suite: `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-gui-energy-final -p no:cacheprovider` — **1220 passed in 59.21 s**. Focused energy-workspace suite: **8 passed**.
- `ruff check src tests` — passed; `ruff format --check src tests` — passed, **268 files already formatted**. The five changed Python files passed scoped Ruff/format. Root-wide `ruff check .` encountered ACL traversal errors plus lint findings in scratch `tmp/*.py`; root-wide `ruff format --check .` panicked on non-source content during traversal. These root-wide checks are not reported as passing.
- `node --check src/hf_tcm/studio/static/scientific.js` and `node --check scripts/qa_gui_energy01.js` — passed.
- Edge QA: `node scripts/qa_gui_energy01.js`, Microsoft Edge via DevTools Protocol, 1366×768 and 1920×1080. Verified single Identity energy, no auto-run, overflow, paired static-multipath Joint/B0/B1 series, stop/resume, 30 unique records, aggregates from stored counts, saved-result load, and visible PNG content. QA JSON: `outputs/repro09/energy-studies/gui-energy-01-exports/gui_energy_01_edge_qa.json`.
- Identity F=32, A=0.5: 256 actual transmitted samples, `E_tx,d=64`, `E_b,d=1=4A²`, zero BER and information-pair SER in Joint/B0; zero-noise γ is undefined. Static multipath F=32, 3 γ points × 10 trials: 30 paired records completed after stop/resume. Each point remains above target BER 0.05, so gain/CI are correctly unavailable; this exploratory GUI acceptance set is not confirmatory evidence.
- BER PNG: 593×250, 148,250/148,250 opaque pixels and 12,650 non-white pixels. Production `load_energy_study` validated the saved study and all manifest hashes. Historical verifier: **694/694**, 76/76 source files, 27 SVGs valid, no failures.
- Final report: `docs/repro/GUI_ENERGY_01_FINAL_REPORT.md`; full audit archive: `HF_TCM_SIM_GUI_ENERGY_01_AUDIT.zip`.

## SCIENTIFIC-EXP-01

Full pytest final:1212 passed in67.75s, fresh workspace-local basetemp/cache disabled. Scoped Ruff src/tests and all new energy scripts passed after import/metadata-probe fixes. Historical verifier694/694 and76/76 passed. Independent replay572manifested series+diagnostic records, maxsignal residual9.93e-16; all bit/pair/frame counts and observation hashes checked. Main statistical dataset553pairs/362112bits:90pilot,461confirmatory,2long. 9 posthoc same-seed scaling comparisons F256 gave identical decoded bits for every applicable arm and waveform differences<1e-15; excluded from inference. PNG/SVG content validation152files passed. Main inference remains incomplete; physical gain not established. Logs and frozen protocol in outputs/scientific_exp_01/.

## SCIENTIFIC-EXP-03A — shared pilot frontend and metric isolation

- Full regression, run sequentially with a workspace-local basetemp and cache disabled: `python -m pytest -q --basetemp tmp/pytest-exp03a-final -p no:cacheprovider` — **1256 passed in 348.93 s**. The 17 new metric-isolation tests separately passed. The first concurrent run had one 30 s timeout in an unchanged EXP-02 GUI route; the same test passed alone in 11.36 s and the subsequent full run passed. `outputs/scientific-exp03a/validation/pytest_retry_note.md` records this.
- Scoped `ruff check` over changed Python modules/scripts/tests and `ruff format --check` over changed Python files — PASS. `ruff check .` was attempted and reports denied ACL paths plus 136 repository/scratch findings; `ruff format --check .` was attempted and Ruff panicked on non-source traversal (`Expected a ruff source file`). Neither root-wide command is reported as passing. Logs: `outputs/scientific-exp03a/validation/{scoped_ruff,scoped_ruff_format,root_ruff,root_ruff_format}.log`.
- Node syntax checks for `scientific_metric.js` and its Edge QA script — PASS. Microsoft Edge actual browser QA — **5/5** checks at 1366×768 and 1920×1080: launch/save a paired static `[0,3]` metric trial, verify/load a saved Rician pilot series, prevent unbracketed gain claims, toggle curves, download PNG/SVG. Evidence and screenshots are in `outputs/scientific-exp03a/validation/edge_gui_qa.json` and `docs/screenshots/scientific-exp03a-metric-rician-*`.
- Independent recount — PASS: 9 range-finding namespaces, 205 paired trials, all observation hashes rebuilt from actual received arrays, paired frontend hashes equal, bit/pair counts and energy recounted. PNG/SVG validation — PASS (4 browser exports plus two nonempty Edge screenshots). See `outputs/scientific-exp03a/validation/`.
- Historical checker: **694/694 fingerprints**, 76/76 REPRO-06B files, 27 SVG documents valid. EXP-02 verifier: PASS; original 2,160 confirmatory frames/source tree unchanged. No confirmatory SCIENTIFIC-EXP-03B trial was started. `paper_exact:false`; article 1.5 dB and physical Eb/N0 are not confirmed.
