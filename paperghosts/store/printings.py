"""A printing's reference, built from its candidate row (decision 33).

- Where it is comes from its member name: the date, a page token, the LCCN, the reel, the issue
  (the date and a two-digit edition) and the frame. Every v2 candidate's parses.
- The LCCN comes from the member name too, when the record has none (0.9% of candidates).
- The page comes from the scan record only, never from the member's page token.
- The IIIF service comes only where the scan has a batch path: the batch path's batch, with the
  member's frame where only the frame differs, as it does in 2.5% of the candidates with both.
  The member's frame was the page in 18 of 18, and that page is checked before its crop is
  shown (decision 35, the EM's call). A printing with no batch path gets no service here. The
  reel-to-batch map gives it one when its crop is fetched, and its page is checked then.
"""

import re

from paperghosts.ingest.crops import BATCH_PATH, MEMBER, batch_path_service
from paperghosts.schemas import Printing


def scan_number(text):
    """A scan record's page ("8") as a number; None for "na", "0" or none."""
    digits = re.sub(r"\D", "", str(text or ""))
    return int(digits) or None if digits else None


def printing(row: dict) -> dict:
    """The printing as it is stored, checked by its model."""
    member = MEMBER.search(row["member"])
    scan = row.get("scan") or {}
    path = BATCH_PATH.search(scan.get("raw_data_loc") or "")
    found = Printing.model_validate(
        {
            "article_id": row["article_id"],
            "lccn": row["lccn"] or member["lccn"],
            "paper": row["paper"],
            "state": row["state"],
            "date": row["date"],
            "edition": int(member["issue"][8:]),
            "reel": member["reel"],
            "issue": member["issue"],
            "frame": member["seq"],
            "page": scan_number(scan.get("page")),
            "service": batch_path_service(row["member"], path.string) if path else None,
            # a box can start a few pixels off the page's edge
            "bbox_list": [
                {k: max(0, int(box[k])) for k in ("x0", "y0", "x1", "y1")}
                for box in row["bbox_list"]
            ],
        }
    )
    return found.model_dump(exclude_none=True)
