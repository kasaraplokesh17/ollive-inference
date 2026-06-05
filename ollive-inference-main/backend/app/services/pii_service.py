import re
from typing import Optional
import structlog

logger = structlog.get_logger()

# Regex-based PII patterns (fallback when presidio not available)
PII_PATTERNS = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]"),
    (r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE]"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),
    (r"\b(?:\d[ -]?){13,16}\b", "[CREDIT_CARD]"),
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP_ADDRESS]"),
    (r"\b[A-Z]{2}\d{6}[A-Z]?\b", "[PASSPORT]"),
]

_presidio_available = False
_analyzer = None
_anonymizer = None


def _init_presidio():
    global _presidio_available, _analyzer, _anonymizer
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()
        _presidio_available = True
        logger.info("Presidio PII engine initialized")
    except Exception as e:
        logger.warning("Presidio not available, using regex fallback", error=str(e))
        _presidio_available = False


def redact_pii(text: Optional[str]) -> Optional[str]:
    if not text:
        return text

    if _presidio_available and _analyzer and _anonymizer:
        try:
            results = _analyzer.analyze(text=text, language="en")
            if results:
                anonymized = _anonymizer.anonymize(text=text, analyzer_results=results)
                return anonymized.text
        except Exception as e:
            logger.warning("Presidio redaction failed, using regex", error=str(e))

    # Regex fallback
    redacted = text
    for pattern, replacement in PII_PATTERNS:
        redacted = re.sub(pattern, replacement, redacted)
    return redacted


def init_pii_engine():
    _init_presidio()
