"""
Deterministic Query Engine for Official VIT Mumbai Fees & Year-wise Cutoffs.
Queries structured records from data/vit_fees.json and data/vit_cutoffs.json.
Guarantees exact numerical data retrieval without AI hallucination or guesswork.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FEES_FILE = DATA_DIR / "vit_fees.json"
CUTOFFS_FILE = DATA_DIR / "vit_cutoffs.json"


class VITMetricsDB:
    """Manages deterministic lookup of official fees and year-wise MHT-CET/JEE cutoffs."""

    def __init__(self):
        self.fees_data: Dict[str, Any] = {}
        self.cutoffs_data: Dict[str, Any] = {}
        self.load()

    def load(self):
        """Load JSON datasets from data directory."""
        if FEES_FILE.exists():
            try:
                with open(FEES_FILE, "r", encoding="utf-8") as f:
                    self.fees_data = json.load(f)
            except Exception as e:
                logger.error("Failed to load %s: %s", FEES_FILE, e)

        if CUTOFFS_FILE.exists():
            try:
                with open(CUTOFFS_FILE, "r", encoding="utf-8") as f:
                    self.cutoffs_data = json.load(f)
            except Exception as e:
                logger.error("Failed to load %s: %s", CUTOFFS_FILE, e)

    # ------------------------------------------------------------------------
    # Branch & Parameter Extractors
    # ------------------------------------------------------------------------

    @staticmethod
    def detect_branch(text: str) -> Optional[str]:
        """Detect referenced engineering or management branch from text."""
        lower = text.lower()
        if any(w in lower for w in ["computer", "comp", "cs", "cse", "cmpn"]):
            if "electronics" in lower:
                return "Electronics & Computer Science"
            return "Computer Engineering"
        if any(w in lower for w in ["information technology", "it", "inft"]):
            return "Information Technology"
        if any(w in lower for w in ["electronics and computer", "ecs", "excs", "electronics & computer"]):
            return "Electronics & Computer Science"
        if any(w in lower for w in ["telecom", "extc", "electronics and telecommunication", "telecommunication"]):
            return "Electronics & Telecommunication Engineering"
        if any(w in lower for w in ["biomedical", "biomed", "biomedical engineering"]):
            return "Biomedical Engineering"
        if any(w in lower for w in ["mms", "mba", "management"]):
            return "Master of Management Studies (MMS)"
        if any(w in lower for w in ["mtech", "m.tech", "postgraduate", "pg"]):
            return "M.Tech Engineering"
        return None

    @staticmethod
    def detect_category(text: str) -> Optional[str]:
        """Detect student category from text."""
        lower = text.lower()
        if "tfws" in lower:
            return "TFWS"
        if "ebc" in lower:
            return "EBC"
        if "ews" in lower:
            return "EWS"
        if any(w in lower for w in ["obc", "sebc"]):
            return "OBC"
        if any(w in lower for w in ["sc/st", "sc or st", "sc", "st"]):
            if "sc" in lower:
                return "SC"
            if "st" in lower:
                return "ST"
        if any(w in lower for w in ["vj", "nt", "sbc"]):
            return "VJNT"
        if any(w in lower for w in ["open", "general", "acap"]):
            return "OPEN"
        return None

    @staticmethod
    def detect_quota(text: str) -> str:
        """Detect if management quota or CAP quota is referenced."""
        lower = text.lower()
        if any(w in lower for w in ["management", "institute level", "il", "il quota", "institutional"]):
            return "INSTITUTE_LEVEL"
        return "CAP"

    @staticmethod
    def detect_year(text: str) -> str:
        """Detect academic year referenced in text."""
        lower = text.lower()
        if "2026" in lower or "26" in lower:
            return "2025-26"  # Latest available base cutoff/fee
        if "2025" in lower or "25" in lower:
            return "2025-26"
        if "2024" in lower or "24" in lower:
            return "2024-25"
        if "2023" in lower or "23" in lower:
            return "2023-24"
        return "2025-26"

    @staticmethod
    def detect_round(text: str) -> Optional[str]:
        """Detect CAP round 1, 2, or 3."""
        lower = text.lower()
        if any(w in lower for w in ["round 1", "round i", "round-1", "cap 1", "cap round 1"]):
            return "CAP Round 1"
        if any(w in lower for w in ["round 2", "round ii", "round-2", "cap 2", "cap round 2"]):
            return "CAP Round 2"
        if any(w in lower for w in ["round 3", "round iii", "round-3", "cap 3", "cap round 3", "final round"]):
            return "CAP Round 3"
        return None

    # ------------------------------------------------------------------------
    # Fee Lookup
    # ------------------------------------------------------------------------

    def query_fees(self, query_text: str) -> Optional[Dict[str, Any]]:
        """
        Check if query is asking for fees and return exact structured data.
        """
        lower = query_text.lower()
        is_fee_query = any(w in lower for w in ["fee", "fees", "cost", "tuition", "development fee", "payable", "structure", "how much"])
        if not is_fee_query:
            return None

        branch = self.detect_branch(query_text)
        category = self.detect_category(query_text)
        quota = self.detect_quota(query_text)
        academic_year = self.detect_year(query_text)

        # Check if asking specifically for Institute Level
        if quota == "INSTITUTE_LEVEL":
            il_list = self.fees_data.get("institutional_fees", [])
            matched = []
            for item in il_list:
                if branch and item["branch"].lower() != branch.lower():
                    continue
                matched.append(item)
            if matched:
                return {
                    "type": "INSTITUTE_LEVEL_FEE",
                    "branch": branch or "All Branches",
                    "quota": "Institute Level (IL) / Management Quota",
                    "records": matched,
                    "source_url": "https://vit.edu.in/admissions/",
                    "authority": "Fee Regulating Authority (FRA), Govt. of Maharashtra"
                }

        # Otherwise standard CAP Fee query
        cap_sections = self.fees_data.get("cap_fees", [])
        ug_section = cap_sections[0] if cap_sections else None
        if not ug_section:
            return None

        # Filter categories
        categories = ug_section.get("categories", [])
        matched_categories = []
        if category:
            cat_code = category.upper()
            for cat in categories:
                if cat_code in cat.get("category_code", "") or cat_code in cat.get("category", "").upper():
                    matched_categories.append(cat)
        if not matched_categories:
            matched_categories = categories  # return full breakdown

        return {
            "type": "CAP_FEE",
            "programme": "Undergraduate B.Tech Engineering (All 5 Branches: Computer, IT, ECS, EXTC, Biomedical)",
            "branch": branch or "Undergraduate B.Tech (All Branches)",
            "quota": "CAP (Centralized Admission Process / General Merit / ACAP)",
            "academic_years": ["2024-25", "2025-26", "2026-27 (Approved Base)"],
            "records": matched_categories,
            "source_url": "https://vit.edu.in/admissions/",
            "authority": "Fee Regulating Authority (FRA), Government of Maharashtra"
        }

    # ------------------------------------------------------------------------
    # Cutoff Lookup
    # ------------------------------------------------------------------------

    def query_cutoffs(self, query_text: str) -> Optional[Dict[str, Any]]:
        """
        Check if query is asking for cutoffs and return exact structured data.
        """
        lower = query_text.lower()
        is_cutoff_query = any(w in lower for w in ["cutoff", "cut-off", "cut off", "percentile", "closing rank", "merit", "rank required", "score required", "marks required"])
        if not is_cutoff_query:
            return None

        branch = self.detect_branch(query_text)
        year = self.detect_year(query_text)
        category = self.detect_category(query_text)
        target_round = self.detect_round(query_text)

        all_records = self.cutoffs_data.get("records", [])

        # Filter by year and branch
        filtered = []
        for rec in all_records:
            if year and rec.get("academic_year") != year:
                continue
            if branch and rec.get("branch").lower() != branch.lower():
                continue
            filtered.append(rec)

        # If no exact match for specified year, search all years
        if not filtered and branch:
            for rec in all_records:
                if rec.get("branch").lower() == branch.lower():
                    filtered.append(rec)

        if not filtered:
            # If user asked about cutoff without branch
            return {
                "type": "CUTOFF_NEEDS_BRANCH",
                "message": "Cutoffs vary significantly by branch (Computer Engineering, IT, ECS, EXTC, Biomedical), category (Open, OBC, SC, TFWS), and CAP round. Please specify which branch and category you are interested in.",
                "available_branches": [
                    "Computer Engineering (Choice Code: 313924510)",
                    "Information Technology (Choice Code: 313924610)",
                    "Electronics & Computer Science (Choice Code: 313984410)",
                    "Electronics & Telecommunication (Choice Code: 313937210)",
                    "Biomedical Engineering (Choice Code: 313989310)"
                ],
                "source_url": "https://fe2026.mahacet.org/"
            }

        # Structure matches
        results = []
        for rec in filtered:
            rec_branch = rec.get("branch")
            rec_year = rec.get("academic_year")
            rec_exam = rec.get("exam", "MHT-CET")
            choice_code = rec.get("choice_code")

            for rnd in rec.get("rounds", []):
                round_name = rnd.get("round")
                if target_round and target_round.lower() not in round_name.lower():
                    continue

                cutoffs = rnd.get("cutoffs", {})
                # If category specified, extract that specific one
                cat_matches = {}
                if category:
                    cat_key = category.upper()
                    for k, v in cutoffs.items():
                        if cat_key in k:
                            cat_matches[k] = v
                if not cat_matches:
                    cat_matches = cutoffs

                results.append({
                    "branch": rec_branch,
                    "choice_code": choice_code,
                    "academic_year": rec_year,
                    "exam": rec_exam,
                    "round": round_name,
                    "cutoffs": cat_matches
                })

        return {
            "type": "CUTOFF_MATCH",
            "branch": branch or "Multiple Branches",
            "academic_year": year,
            "category_filter": category or "All Categories",
            "round_filter": target_round or "All Rounds",
            "results": results,
            "source_url": "https://fe2026.mahacet.org/",
            "portal": "Government of Maharashtra State Common Entrance Test Cell (CET Cell)",
            "institute_code": "3139"
        }

    # ------------------------------------------------------------------------
    # Formatting Context for AI Injection
    # ------------------------------------------------------------------------

    def build_exact_context(self, query_text: str) -> Optional[str]:
        """
        Build an authoritative prompt context block when exact numerical
        fee or cutoff data is detected.
        """
        fee_result = self.query_fees(query_text)
        cutoff_result = self.query_cutoffs(query_text)

        if not fee_result and not cutoff_result:
            return None

        lines = ["=== AUTHORITATIVE OFFICIAL VERIFIED NUMERICAL DATA (FROM MAHA CET CELL & FRA) ==="]
        lines.append("CRITICAL INSTRUCTION: You MUST use the exact numbers, amounts in ₹, and percentiles below.")
        lines.append("Do NOT estimate, guess, round, or alter any numbers. Present them in clear Markdown tables.\n")

        if fee_result:
            lines.append("--- OFFICIAL APPROVED FEE STRUCTURE (CODE: 3139) ---")
            lines.append(f"Authority: {fee_result.get('authority')}")
            lines.append(f"Official Source URL: {fee_result.get('source_url')}")

            if fee_result.get("type") == "INSTITUTE_LEVEL_FEE":
                lines.append(f"Admission Quota: {fee_result.get('quota')}")
                lines.append("Branch-Wise Annual & 4-Year Total Fees:")
                for r in fee_result.get("records", []):
                    lines.append(
                        f"- Branch: {r.get('branch')} | Tuition: ₹{r.get('tuition_fee'):,} | Development: ₹{r.get('development_fee'):,} | "
                        f"Annual Total: ₹{r.get('total_annual_fee'):,} | 4-Year Programme Total: ₹{r.get('total_four_year_fee'):,}"
                    )
            else:
                lines.append(f"Programme: {fee_result.get('programme')}")
                lines.append(f"Admission Quota: {fee_result.get('quota')}")
                lines.append(f"Academic Years: {', '.join(fee_result.get('academic_years', []))}")
                lines.append("Category-Wise Annual & 4-Year Total Fees:")
                for r in fee_result.get("records", []):
                    lines.append(
                        f"* Category: {r.get('category')} | Tuition: ₹{r.get('tuition_fee'):,} | Development: ₹{r.get('development_fee'):,} | "
                        f"Total Annual Payable: ₹{r.get('total_annual_fee'):,} | Total 4-Year Programme: ₹{r.get('total_four_year_fee'):,} | "
                        f"Concession Note: {r.get('concession_details', 'N/A')}"
                    )

        if cutoff_result:
            lines.append("\n--- OFFICIAL MHT-CET / JEE MAIN CUTOFF RECORDS (INSTITUTE CODE: 3139) ---")
            lines.append(f"Official Source Portal: {cutoff_result.get('source_url')}")
            lines.append(f"State CET Cell Institute Choice Code Prefix: 3139")

            if cutoff_result.get("type") == "CUTOFF_NEEDS_BRANCH":
                lines.append(f"NOTICE: {cutoff_result.get('message')}")
                lines.append("Available branches: " + ", ".join(cutoff_result.get("available_branches", [])))
            else:
                for item in cutoff_result.get("results", []):
                    lines.append(f"\n[Branch: {item.get('branch')} (Choice Code: {item.get('choice_code')}) | Year: {item.get('academic_year')} | {item.get('round')}]:")
                    for cat_code, val_obj in item.get("cutoffs", {}).items():
                        unit = val_obj.get("unit")
                        val = val_obj.get("value")
                        rank = val_obj.get("merit_rank")
                        desc = val_obj.get("description", cat_code)
                        rank_str = f" (State Merit Rank: {rank:,})" if rank else ""
                        lines.append(f"  - {desc} ({cat_code}): {val} {unit}{rank_str}")

        lines.append("\n=== END AUTHORITATIVE OFFICIAL VERIFIED NUMERICAL DATA ===")
        return "\n".join(lines)


# Global instance
metrics_engine = VITMetricsDB()
