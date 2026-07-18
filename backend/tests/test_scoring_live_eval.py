"""Live model evals -- unlike the rest of the suite, these call the real
OpenAI API with a real key instead of a fake client, because the bug they
guard against is a model judgment call (domain-mismatch scoring) that a
mocked-response test can't exercise. Opt-in only: set RUN_LIVE_EVALS=1 and a
real OPENAI_API_KEY before running pytest.

    RUN_LIVE_EVALS=1 OPENAI_API_KEY=sk-... pytest tests/test_scoring_live_eval.py
"""

import os

import pytest

from app.scraping.scoring import extract_and_score

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_EVALS"),
    reason="live model eval -- set RUN_LIVE_EVALS=1 and a real OPENAI_API_KEY to run",
)

EVENT_COMPANY_PROFILE = """Seventeam (seventeam.uz), Tashkent, Uzbekistan. MICE-agentstvo i \
Destination Management Company (DMC) polnogo tsikla. Organizuem delovye i korporativnye \
meropriyatiya pod klyuch -- konferentsii, forumy, seminary, vystavki, delovye vstrechi, \
insentiv-tury, delovye poezdki i delegatsii. Klyuchevye kompetentsii: organizatsiya \
konferentsiy/forumov/seminarov/vystavok pod klyuch, arenda i podbor konferents-zalov, \
transportnoe obsluzhivanie delegatsiy, transfery, keyтering i banketnoe obsluzhivanie, \
gostinichnoe razmeshchenie grupp, vizovaya podderzhka, uslugi perevodchikov i protokolnoe \
soprovozhdenie. Net opyta v IT, razrabotke programmnogo obespecheniya ili sistem."""

IT_SYSTEM_TENDER_CONTENT = """Tender #44: AEDS Development IT System Advisor
Organization: World Bank
Deadline: 16.07.2026
Scope of work: advise on the design, architecture, and implementation of an
enterprise IT system (AEDS) for asset and expenditure data management,
including database design, software development oversight, and systems
integration with existing government platforms. Requires demonstrated prior
experience delivering IT systems / software development projects."""


def test_scoring_rejects_it_tender_for_event_management_company():
    """Reproduces the exact screenshot bug: an events/MICE company was scored
    50% compliant on a pure IT-systems-development World Bank tender, justified
    as 'a chance to expand competencies in IT systems.' That reasoning must not
    survive the domain-match rule added to the scoring prompt."""
    tenders = extract_and_score(
        IT_SYSTEM_TENDER_CONTENT,
        {"name": "World Bank", "url": "https://worldbank.org"},
        EVENT_COMPANY_PROFILE,
    )

    assert tenders, "expected the tender to be extracted from the content"
    tender = tenders[0]
    assert tender["compliance"] <= 20, f"compliance too high for a domain mismatch: {tender}"
    assert tender["recommendation"] == "Пропустить", f"should be skipped, got: {tender}"


HUGE_BUDGET_MISMATCHED_TENDER = """Tender #91: Nationwide Core Banking Platform Replacement
Organization: World Bank
Budget: $45,000,000
Deadline: 01.09.2026
Scope of work: replace the core banking platform for a national development
bank -- ledger engine, payments switch, regulatory reporting, and a
multi-year systems integration program. Requires a prime contractor with a
proven core banking software delivery track record."""


def test_scoring_does_not_let_huge_budget_inflate_compliance_for_wrong_sector():
    """A massive, prestigious budget must not buy compliance points for a
    company whose profile has nothing to do with the tender's sector -- the
    same failure mode as the IT-advisor bug, but disguised behind a much
    bigger number that could tempt the model into 'too good to skip'."""
    tenders = extract_and_score(
        HUGE_BUDGET_MISMATCHED_TENDER,
        {"name": "World Bank", "url": "https://worldbank.org"},
        EVENT_COMPANY_PROFILE,
    )

    assert tenders
    tender = tenders[0]
    assert tender["compliance"] <= 20, f"budget size inflated compliance: {tender}"
    assert tender["recommendation"] == "Пропустить", f"should be skipped, got: {tender}"


GENUINE_MATCH_TENDER = """Tender #12: Organization of the Annual Central Asia Investment Forum
Organization: Ministry of Investment, Republic of Uzbekistan
Budget: 850 000 000 UZS
Deadline: 20.09.2026
Scope of work: full-cycle organization of a 3-day international investment
forum for 500 delegates -- venue and conference hall booking, stage and AV
production, delegate transport and transfers, catering and gala dinner,
group hotel accommodation, visa support letters for foreign delegates,
simultaneous interpretation, and protocol/VIP handling. Bidder must
demonstrate prior experience organizing forums or conferences of comparable
scale."""


def test_scoring_still_rewards_a_genuine_sector_match_after_stricter_rule():
    """Regression check for the opposite failure: the new domain-match
    language must not make the model so trigger-happy on 'mismatch' that it
    also tanks a tender that is a textbook match for an events/MICE/DMC
    company's actual stated services."""
    tenders = extract_and_score(
        GENUINE_MATCH_TENDER,
        {"name": "eTender UzEx", "url": "https://etender.uzex.uz"},
        EVENT_COMPANY_PROFILE,
    )

    assert tenders
    tender = tenders[0]
    assert tender["compliance"] >= 70, f"under-scored a genuine sector match: {tender}"
    assert tender["recommendation"] in ("Подать заявку", "Рассмотреть"), tender
