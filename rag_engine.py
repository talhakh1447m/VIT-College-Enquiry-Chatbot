"""
Retrieval-Augmented Generation (RAG) Engine for VIT Mumbai College Enquiry Chatbot.
Grounds chatbot responses exclusively on official information from https://vit.edu.in/.
Features:
- Academic acronym normalization & TF-IDF style relevance scoring
- Rich verified chunks (Admissions, Courses, Comparisons, Placements, Fees, Campus)
- Real-time live web verification with in-memory TTL caching for latest notices
- Source citation metadata and on-demand live re-indexing
"""

import json
import logging
import math
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
KB_FILE = DATA_DIR / "vit_knowledge_base.json"

OFFICIAL_PAGES = [
    {
        "category": "Institute Overview",
        "title": "About VIT Mumbai & Institute Profile",
        "url": "https://vit.edu.in/about-us/",
        "priority": 1.2
    },
    {
        "category": "Admissions",
        "title": "Admissions Hub & Central Portal",
        "url": "https://vit.edu.in/admissions/",
        "priority": 1.4
    },
    {
        "category": "Undergraduate Admissions",
        "title": "B.Tech Undergraduate Admissions (First Year)",
        "url": "https://vit.edu.in/admission-engineering-ug/",
        "priority": 1.5
    },
    {
        "category": "Lateral Entry Admissions",
        "title": "Direct Second Year (DSE) Engineering Admissions",
        "url": "https://vit.edu.in/admission-engineering-lateral-entry/",
        "priority": 1.3
    },
    {
        "category": "Postgraduate Admissions",
        "title": "M.Tech Engineering Admissions",
        "url": "https://vit.edu.in/admission-engineering-pg/",
        "priority": 1.2
    },
    {
        "category": "Management Admissions",
        "title": "MMS (Master of Management Studies) Admissions",
        "url": "https://vit.edu.in/admission-mms/",
        "priority": 1.2
    },
    {
        "category": "Placements",
        "title": "Training & Placement Cell Information",
        "url": "https://vit.edu.in/placement/",
        "priority": 1.4
    },
    {
        "category": "Contact & Campus",
        "title": "Campus Location, Directions & Contact Information",
        "url": "https://vit.edu.in/contact/",
        "priority": 1.5
    },
    {
        "category": "Academics",
        "title": "Credit Transfer Courses & Academic Offerings",
        "url": "https://vit.edu.in/credit-transfer-course/",
        "priority": 1.0
    }
]

# Comprehensive verified knowledge base covering all facets of VIT Mumbai.
DEFAULT_CHUNKS = [
    {
        "id": "vit-general-overview",
        "title": "Vidyalankar Institute of Technology (VIT), Mumbai Overview",
        "url": "https://vit.edu.in/about-us/",
        "category": "Institute Overview",
        "content": (
            "Vidyalankar Institute of Technology (VIT) is an engineering and management institute situated at "
            "Wadala (East), Mumbai - 400037, Maharashtra. Established in 1999, it is an Autonomous Institute "
            "permanently affiliated to the University of Mumbai, approved by the All India Council for Technical Education (AICTE), "
            "and recognized by the Directorate of Technical Education (DTE), Government of Maharashtra.\n"
            "Accreditation & Recognition:\n"
            "- NAAC Grade 'A+' accredited institute.\n"
            "- National Board of Accreditation (NBA) accredited eligible engineering programs.\n"
            "- Known for its modern infrastructure, industry-academic alliances, and vibrant student life."
        ),
        "keywords": ["vit", "mumbai", "vidyalankar", "overview", "naac", "a+", "autonomous", "aicte", "university of mumbai", "wadala", "accreditation", "established 1999"]
    },
    {
        "id": "vit-btech-programs-overview",
        "title": "Undergraduate B.Tech Degree Programs Offered",
        "url": "https://vit.edu.in/admission-engineering-ug/",
        "category": "Courses",
        "content": (
            "VIT Mumbai offers 4-year full-time Undergraduate Bachelor of Technology (B.Tech) degree programs:\n"
            "1. Computer Engineering: Focuses on software engineering, algorithms, cloud computing, operating systems, and distributed systems.\n"
            "2. Information Technology (IT): Emphasizes software design, web technologies, database management, cybersecurity, and data analytics.\n"
            "3. Electronics & Computer Science (ECS): Blends embedded hardware systems with modern computer science, algorithms, and AI/ML.\n"
            "4. Electronics & Telecommunication Engineering (EXTC): Covers wireless communication, 5G/IoT networks, RF systems, signal processing, and robotics.\n"
            "5. Biomedical Engineering: Bridges medical healthcare technologies, clinical instrumentation, biomechanics, and physiological signal analysis.\n"
            "Curriculum highlights: Autonomous curriculum designed with industry inputs, offering Honors and Minor degrees, credit transfer programs, and extensive project-based learning."
        ),
        "keywords": ["btech", "courses", "branches", "programs", "computer engineering", "it", "information technology", "extc", "ecs", "biomedical", "degrees", "undergraduate", "ug", "curriculum"]
    },
    {
        "id": "vit-branch-comparison",
        "title": "Comparison of Engineering Branches at VIT Mumbai",
        "url": "https://vit.edu.in/admission-engineering-ug/",
        "category": "Courses",
        "content": (
            "Choosing between engineering disciplines at VIT Mumbai:\n"
            "- Computer Engineering vs Information Technology: Computer Engineering deals deeply with computing architecture, systems programming, and algorithms, while IT focuses on enterprise applications, data management, cloud computing, and cyber security. Both share outstanding placement opportunities in top software and consulting firms.\n"
            "- Electronics & Computer Science (ECS): Best for students who want dual expertise in software programming and hardware/IoT interfacing. Prepares graduates for both tech software roles and embedded systems/semiconductor careers.\n"
            "- Electronics & Telecommunication (EXTC): Focuses on telecommunications, IoT, embedded systems, and robotics with high placement overlap in tech companies and telecom giants.\n"
            "- Biomedical Engineering: Distinct niche field combining engineering principles with medical instrumentation, medical imaging, and healthcare diagnostics."
        ),
        "keywords": ["compare", "comparison", "difference", "computer vs it", "ecs vs extc", "branch selection", "which branch", "career options", "courses"]
    },
    {
        "id": "vit-ug-admission-process",
        "title": "First Year B.Tech Engineering Admission Process & Eligibility",
        "url": "https://vit.edu.in/admission-engineering-ug/",
        "category": "Admissions",
        "content": (
            "First Year Engineering Admissions are conducted under the Centralized Admission Process (CAP) "
            "administered by the State Common Entrance Test Cell, Maharashtra.\n"
            "Eligibility Requirements:\n"
            "1. Candidate must be an Indian National.\n"
            "2. Passed HSC (Std. XII) or its equivalent examination with Physics and Mathematics as compulsory subjects, along with one of Chemistry, Biotechnology, Biology, Technical Vocational subject, Computer Science, or Information Technology.\n"
            "3. Obtained at least 45% marks (at least 40% marks for backward class categories, EWS, and PwD candidates of Maharashtra State).\n"
            "4. Valid score in MHT-CET (for Maharashtra State quota) or JEE (Main) Paper-I (for All India seats).\n"
            "Step-by-step CAP Round Process:\n"
            "- Step 1: Online registration on the State CET Cell portal (https://cetcell.mahacet.org/).\n"
            "- Step 2: Document verification and confirmation at Facilitation Centers (FC) / e-Scrutiny.\n"
            "- Step 3: Display of Provisional and Final Merit Lists.\n"
            "- Step 4: Online Option Form submission for CAP Rounds (choice filling of VIT college code).\n"
            "- Step 5: Seat Allotment (Freeze / Betterment) and reporting to the institute with original documents and fees.\n"
            "Institutional / Against CAP vacancy seats are notified on https://vit.edu.in/admission-engineering-ug/."
        ),
        "keywords": ["admission", "eligibility", "btech", "first year", "cap", "cap round", "mht-cet", "jee main", "dte", "cet cell", "criteria", "entrance exam", "steps", "documents", "process"]
    },
    {
        "id": "vit-lateral-entry",
        "title": "Direct Second Year Engineering (DSE / Lateral Entry) Admissions",
        "url": "https://vit.edu.in/admission-engineering-lateral-entry/",
        "category": "Admissions",
        "content": (
            "Diploma holders and B.Sc. graduates can seek direct admission into the 2nd Year (Semester 3) of B.Tech programs.\n"
            "Eligibility Criteria:\n"
            "- Passed 3-year AICTE-approved Diploma in Engineering & Technology with at least 45% marks (40% for reserved/EWS/PwD candidates from Maharashtra).\n"
            "- OR passed B.Sc. Degree from a recognized UGC university with at least 45% marks (40% for reserved candidates) and passed Std. XII with Mathematics.\n"
            "Admission Route: Administered through Maharashtra State CET Cell CAP rounds. Visit https://vit.edu.in/admission-engineering-lateral-entry/ for current year category cutoffs and intake notices."
        ),
        "keywords": ["direct second year", "dse", "lateral entry", "diploma", "polytechnic", "second year", "admission", "cap", "b.sc"]
    },
    {
        "id": "vit-pg-programs",
        "title": "Postgraduate M.Tech Engineering Admissions & Specializations",
        "url": "https://vit.edu.in/admission-engineering-pg/",
        "category": "Courses",
        "content": (
            "VIT Mumbai offers Master of Technology (M.Tech) degrees for engineering graduates:\n"
            "- M.Tech in Computer Engineering\n"
            "- M.Tech in Electronics & Telecommunication Engineering\n"
            "Eligibility: Bachelor's degree in relevant branch of engineering (B.E./B.Tech) with at least 50% marks (45% for reserved categories) and a qualifying GATE score or sponsored candidate criteria as prescribed by DTE Maharashtra.\n"
            "Official page: https://vit.edu.in/admission-engineering-pg/"
        ),
        "keywords": ["mtech", "postgraduate", "pg", "master", "gate", "computer engineering", "extc", "admission"]
    },
    {
        "id": "vit-mms-program",
        "title": "Master of Management Studies (MMS) Admissions",
        "url": "https://vit.edu.in/admission-mms/",
        "category": "Courses",
        "content": (
            "The 2-year full-time MMS program at VIT Mumbai is approved by AICTE and affiliated to University of Mumbai.\n"
            "Specializations Offered: Finance, Marketing, Human Resources (HR), Operations, and Systems.\n"
            "Eligibility & Admission:\n"
            "- Bachelor's Degree of minimum 3 years duration with minimum 50% aggregate marks (45% for reserved categories of Maharashtra).\n"
            "- Valid percentile score in MAH-MBA/MMS-CET, CAT, or CMAT.\n"
            "- Admissions are processed through State CET Cell CAP Rounds. Official page: https://vit.edu.in/admission-mms/"
        ),
        "keywords": ["mms", "mba", "management", "business", "mah-cet", "cat", "cmat", "admission", "finance", "marketing", "hr", "operations"]
    },
    {
        "id": "vit-placements",
        "title": "Training & Placement Cell and Career Support",
        "url": "https://vit.edu.in/placement/",
        "category": "Placements",
        "content": (
            "VIT Mumbai has a dedicated Training and Placement (T&P) Cell that prepares students throughout their degree:\n"
            "- Pre-placement training: Coding challenges, data structures bootcamps, aptitude preparation, group discussion practice, and mock technical interviews with corporate alumni.\n"
            "- Top Recruiters: TCS, Infosys, Capgemini, LTI (L&T Infotech), Reliance Jio, Barclays, Worley, Zeus Learning, Media.net, Morgan Stanley, and emerging product startups.\n"
            "- Internship Support: Summer and winter industrial internships arranged with leading tech firms.\n"
            "Official Placement Page: https://vit.edu.in/placement/ (provides audited annual batch reports, highest packages, average CTC, and recruiter brochures)."
        ),
        "keywords": ["placement", "jobs", "recruiters", "salary", "package", "tcs", "infosys", "highest package", "average package", "companies", "internships", "training and placement", "t&p"]
    },
    {
        "id": "vit-fees-scholarships",
        "title": "Fee Structure & Government Scholarship Guidelines",
        "url": "https://vit.edu.in/admissions/",
        "category": "Fees",
        "content": (
            "Academic tuition and development fees at VIT Mumbai are officially determined annually by the Fee Regulating Authority (FRA), Government of Maharashtra.\n"
            "Scholarships & Concessions:\n"
            "- Economically Backward Class (EBC): 50% tuition fee waiver for eligible students via the MahaDBT portal.\n"
            "- Tuition Fee Waiver Scheme (TFWS): 100% tuition fee waiver for top meritorious students allotted through CAP TFWS seats.\n"
            "- Reserved Categories (SC / ST / VJNT / SBC / OBC): Government scholarship schemes covering partial or full tuition/exam fees as per social justice department norms.\n"
            "- Official fee circulars: Because fees and installment schedules are governed by FRA regulatory circulars, candidates must inspect the authenticated fee schedule at https://vit.edu.in/admissions/."
        ),
        "keywords": ["fees", "fee structure", "cost", "scholarship", "fra", "mahadbt", "ebc", "tfws", "sc", "st", "obc", "installment", "tuition fee"]
    },
    {
        "id": "vit-campus-facilities",
        "title": "Campus Life, Labs, Library & Student Facilities",
        "url": "https://vit.edu.in/about-us/",
        "category": "Campus",
        "content": (
            "Campus Facilities at Vidyalankar Educational Campus, Wadala:\n"
            "- Smart Classrooms: Centrally air-conditioned amphitheater-style classrooms with high-resolution digital projection.\n"
            "- Advanced Labs: Apple iOS developer lab, IoT/AI research laboratories, High-Performance Computing (HPC) lab, and robotics cell.\n"
            "- Central Library: Extensive collection of text and reference books, national/international journals, e-books, IEEE digital library access, and reading halls.\n"
            "- Student Bodies & Activities: IEEE Student Branch, ACM Chapter, CSI, Entrepreneurship Cell (E-Cell), Verve annual cultural festival, and inter-collegiate sports events."
        ),
        "keywords": ["campus", "facilities", "library", "labs", "smart classroom", "wifi", "sports", "canteen", "infrastructure", "clubs", "verve", "events", "apple lab"]
    },
    {
        "id": "vit-contact-location",
        "title": "VIT Mumbai Campus Location & Official Contact Information",
        "url": "https://vit.edu.in/contact/",
        "category": "Contact",
        "content": (
            "Campus Address:\n"
            "Vidyalankar Institute of Technology, Vidyalankar Educational Campus, Vidyalankar College Marg, Wadala (East), Mumbai - 400 037, Maharashtra, India.\n"
            "Commuting & Accessibility:\n"
            "- Closest Harbour Line Station: Wadala Road Station (approx. 10-15 minutes by share cab/bus).\n"
            "- Closest Central/Western Junction: Dadar Station (approx. 15-20 minutes by cab/bus).\n"
            "- Monorail: Vadala Bridge / Bhakti Park monorail stations are nearby.\n"
            "Official Contact Portal: https://vit.edu.in/contact/\n"
            "Administrative Working Hours: Monday to Saturday during standard college office hours."
        ),
        "keywords": ["contact", "address", "location", "phone", "email", "office", "reach", "wadala", "mumbai", "directions", "station", "dadar", "monorail"]
    }
]


class VITKnowledgeBase:
    """Manages indexing, retrieval, live verification, and search for official VIT information."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or KB_FILE
        self.chunks: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {
            "source": "https://vit.edu.in/",
            "last_updated": None,
            "chunk_count": 0
        }
        # In-memory live page cache: { url: { "content": ..., "timestamp": ..., "title": ... } }
        self._live_cache: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        """Load knowledge base from disk or initialize with rich defaults."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.chunks = data.get("chunks", [])
                    self.metadata = data.get("metadata", self.metadata)
                    logger.info("Loaded %d knowledge chunks from %s", len(self.chunks), self.storage_path)
                    return
            except Exception as e:
                logger.warning("Error reading %s (%s). Rebuilding defaults.", self.storage_path, e)

        # Initialize defaults
        self.chunks = list(DEFAULT_CHUNKS)
        self.metadata = {
            "source": "https://vit.edu.in/",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "chunk_count": len(self.chunks)
        }
        self.save()

    def save(self) -> None:
        """Persist knowledge base to disk."""
        self.metadata["chunk_count"] = len(self.chunks)
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({
                    "metadata": self.metadata,
                    "official_pages": OFFICIAL_PAGES,
                    "chunks": self.chunks
                }, f, indent=2, ensure_ascii=False)
        except (OSError, PermissionError) as e:
            logger.warning("Could not persist knowledge base to %s (%s). Operating in-memory.", self.storage_path, e)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenizer with academic acronym normalization and stop-word filtering."""
        stop_words = {
            "a", "an", "the", "and", "or", "of", "to", "in", "for", "on", "with",
            "at", "by", "from", "is", "are", "was", "were", "be", "this", "that",
            "what", "how", "where", "can", "i", "you", "me", "my", "please", "tell",
            "about", "vit", "mumbai", "college", "vidyalankar"
        }
        normalized = text.lower()
        normalized = re.sub(r"\bb[\.\s]?tech\b", " btech tech engineering undergraduate ", normalized)
        normalized = re.sub(r"\bm[\.\s]?tech\b", " mtech master postgraduate ", normalized)
        normalized = re.sub(r"\bm[\.\s]?m[\.\s]?s\b", " mms mba management ", normalized)
        normalized = re.sub(r"\bd[\.\s]?s[\.\s]?e\b", " dse lateral direct second year polytechnic diploma ", normalized)
        normalized = re.sub(r"\bfees?\b", " fees fee structure tuition cost ", normalized)
        normalized = re.sub(r"\bplacement\b", " placement jobs recruiters ctc salary package ", normalized)
        tokens = re.findall(r"[a-z0-9]+", normalized)
        return [t for t in tokens if t not in stop_words and len(t) > 1]

    def verify_live_page(self, url: str, timeout: int = 6) -> Optional[str]:
        """
        Conditionally fetch real-time content from vit.edu.in with TTL caching.
        Prevents excessive requests while verifying fast-changing announcements.
        """
        now = time.time()
        # Check cache (15-minute TTL)
        if url in self._live_cache:
            entry = self._live_cache[url]
            if now - entry["timestamp"] < 900:
                return entry["content"]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VIT-Enquiry-Assistant/3.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as res:
                if res.status == 200:
                    html = res.read().decode("utf-8", errors="ignore")
                    soup = BeautifulSoup(html, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                        tag.decompose()

                    paragraphs = []
                    for el in soup.find_all(["h1", "h2", "h3", "p", "li"]):
                        text = el.get_text(separator=" ", strip=True)
                        if len(text) > 25 and not any(skip in text.lower() for skip in ["cookie", "privacy policy", "copyright"]):
                            paragraphs.append(text)

                    extracted = re.sub(r"\s+", " ", " ".join(paragraphs[:15])).strip()
                    if extracted:
                        self._live_cache[url] = {
                            "content": extracted[:1800],
                            "timestamp": now
                        }
                        logger.info("Successfully live-verified %s", url)
                        return extracted[:1800]
        except Exception as e:
            logger.debug("Live fetch for %s skipped (%s)", url, e)

        return None

    def search(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Retrieve relevant official knowledge chunks with intent boosting.
        If the query requests current notices/deadlines, triggers live page verification.
        """
        query_tokens = self._tokenize(query)
        query_lower = query.lower()

        is_ug = any(w in query_lower for w in ["btech", "b.tech", "ug", "undergraduate", "first year", "fe"])
        is_pg = any(w in query_lower for w in ["mtech", "m.tech", "pg", "postgraduate", "master"])
        is_lateral = any(w in query_lower for w in ["lateral", "direct second year", "dse", "diploma", "polytechnic"])
        is_realtime = any(w in query_lower for w in ["current", "latest", "notice", "deadline", "date", "2026", "2027", "schedule", "cutoff", "fee", "cap round"])

        scored_chunks: List[Tuple[float, Dict[str, Any]]] = []

        for chunk in self.chunks:
            score = 0.0
            content_lower = chunk.get("content", "").lower()
            title_lower = chunk.get("title", "").lower()
            category = chunk.get("category", "")
            keywords = [k.lower() for k in chunk.get("keywords", [])]

            # 1. Exact phrase matches in title/content
            if len(query.strip()) > 3 and query_lower in content_lower:
                score += 6.0
            if len(query.strip()) > 3 and query_lower in title_lower:
                score += 9.0

            # 2. Token overlap with content, title, and keywords
            for token in query_tokens:
                if token in title_lower:
                    score += 4.5
                if any(token == kw or token in kw for kw in keywords):
                    score += 3.5
                freq = content_lower.count(token)
                if freq > 0:
                    score += 1.0 + math.log(1 + freq)

            # Degree Level Matching
            if is_ug:
                if "undergraduate" in title_lower or "b.tech" in title_lower or category == "Undergraduate Admissions":
                    score += 12.0
                if "postgraduate" in title_lower or "m.tech" in title_lower:
                    score -= 8.0
            if is_pg:
                if "postgraduate" in title_lower or "m.tech" in title_lower or category == "Postgraduate Admissions":
                    score += 12.0
                if "undergraduate" in title_lower or "b.tech" in title_lower:
                    score -= 6.0
            if is_lateral:
                if "lateral" in title_lower or "direct second year" in title_lower or category == "Lateral Entry Admissions":
                    score += 14.0

            # Topic Boosts
            if any(w in query_lower for w in ["fee", "fees", "cost", "scholarship", "tuition"]):
                if category == "Fees" or "fee" in title_lower:
                    score += 10.0
            if any(w in query_lower for w in ["placement", "salary", "package", "recruiter", "job"]):
                if category == "Placements" or "placement" in title_lower:
                    score += 10.0
            if any(w in query_lower for w in ["admission", "apply", "eligibility", "cut off", "cet", "jee"]):
                if "admission" in category.lower() or "admission" in title_lower:
                    score += 8.0
            if any(w in query_lower for w in ["course", "branch", "engineering", "btech", "program", "compare"]):
                if category == "Courses" or "degree" in title_lower:
                    score += 7.0
            if any(w in query_lower for w in ["contact", "phone", "email", "address", "location", "reach", "where"]):
                if category == "Contact" or "contact" in title_lower:
                    score += 10.0

            if score > 0:
                scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        results = [c for _, c in scored_chunks[:top_k]]

        if not results and self.chunks:
            results = self.chunks[:2]

        # 3. If real-time / current notices requested, perform live verification on top chunk URL
        if is_realtime and results:
            target_url = results[0].get("url")
            if target_url and target_url.startswith("https://vit.edu.in/"):
                live_text = self.verify_live_page(target_url)
                if live_text:
                    live_chunk = {
                        "id": f"live-verified-{int(time.time())}",
                        "title": f"Live Official Notice Check: {results[0].get('title')}",
                        "url": target_url,
                        "category": results[0].get("category", "Live Official"),
                        "content": live_text,
                        "is_live_verified": True,
                        "verified_at": datetime.now(timezone.utc).isoformat()
                    }
                    results.insert(0, live_chunk)

        return results

    def refresh(self, pages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Crawl official pages from vit.edu.in, extract clean text,
        and update the knowledge base.
        """
        pages_to_crawl = pages or OFFICIAL_PAGES
        scraped_chunks: List[Dict[str, Any]] = []
        errors: List[str] = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VIT-Enquiry-Assistant/3.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        for p in pages_to_crawl:
            url = p["url"]
            title = p.get("title", "VIT Page")
            category = p.get("category", "General")
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=12) as response:
                    if response.status == 200:
                        html = response.read().decode("utf-8", errors="ignore")
                        soup = BeautifulSoup(html, "html.parser")

                        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                            tag.decompose()

                        extracted_text = []
                        for element in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
                            t = element.get_text(separator=" ", strip=True)
                            if len(t) > 20 and not any(skip in t.lower() for skip in ["cookie", "privacy policy", "copyright"]):
                                extracted_text.append(t)

                        full_text = " ".join(extracted_text)
                        clean_text = re.sub(r"\s+", " ", full_text).strip()

                        if len(clean_text) > 100:
                            chunk_size = 1200
                            paragraphs = clean_text.split(". ")
                            current_chunk = []
                            current_len = 0
                            part_idx = 1

                            for para in paragraphs:
                                current_chunk.append(para)
                                current_len += len(para)
                                if current_len >= chunk_size:
                                    chunk_text = ". ".join(current_chunk) + "."
                                    chunk_id = f"scraped-{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}-{part_idx}"
                                    scraped_chunks.append({
                                        "id": chunk_id,
                                        "title": f"{title} (Part {part_idx})" if part_idx > 1 else title,
                                        "url": url,
                                        "category": category,
                                        "content": chunk_text[:2000],
                                        "keywords": self._tokenize(title + " " + category),
                                        "scraped_at": datetime.now(timezone.utc).isoformat()
                                    })
                                    current_chunk = []
                                    current_len = 0
                                    part_idx += 1
                                    if part_idx > 4:
                                        break

                            if current_chunk:
                                chunk_text = ". ".join(current_chunk) + "."
                                chunk_id = f"scraped-{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}-{part_idx}"
                                scraped_chunks.append({
                                    "id": chunk_id,
                                    "title": f"{title} (Part {part_idx})" if part_idx > 1 else title,
                                    "url": url,
                                    "category": category,
                                    "content": chunk_text[:2000],
                                    "keywords": self._tokenize(title + " " + category),
                                    "scraped_at": datetime.now(timezone.utc).isoformat()
                                })
            except Exception as e:
                err_msg = f"Failed to crawl {url}: {str(e)}"
                logger.warning(err_msg)
                errors.append(err_msg)

        if scraped_chunks:
            seen_ids = set()
            merged_chunks = []
            for c in DEFAULT_CHUNKS + scraped_chunks:
                cid = c.get("id")
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    merged_chunks.append(c)

            self.chunks = merged_chunks
            self.metadata["last_updated"] = datetime.now(timezone.utc).isoformat()
            self.metadata["chunk_count"] = len(self.chunks)
            self.save()

        return {
            "status": "completed",
            "chunks_total": len(self.chunks),
            "new_chunks_added": len(scraped_chunks),
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global instance
kb_engine = VITKnowledgeBase()
