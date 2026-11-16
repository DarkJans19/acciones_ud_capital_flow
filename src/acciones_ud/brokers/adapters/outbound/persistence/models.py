"""Query mappings only; 0009 owns the schema and all integrity constraints."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from acciones_ud.brokers.domain import entities as e
from acciones_ud.shared.infrastructure.entity_repository import entity_table

metadata = sa.MetaData()
profiles = entity_table(metadata, "broker_profiles", e.BrokerProfile, ("broker_id",))
profiles.c.certifications.type = ARRAY(sa.Text())
links = entity_table(metadata, "broker_links", e.Link, ("id",))
authorizations = entity_table(
    metadata, "broker_trading_authorizations", e.TradingAuthorization, ("id",)
)
proposals = entity_table(metadata, "broker_proposals", e.Proposal, ("id",))
versions = entity_table(
    metadata, "broker_proposal_versions", e.ProposalVersion, ("proposal_id", "version")
)
versions.c.qty.type = sa.Numeric(20, 9)
for name in ("limit_price", "reference_price"):
    versions.c[name].type = sa.Numeric(18, 4)
versions.c.estimated_cost.type = sa.Numeric(20, 2)
decisions = entity_table(metadata, "broker_proposal_decisions", e.ProposalDecision, ("id",))
decisions.c.evidence_message_ids.type = ARRAY(sa.Uuid())
messages = entity_table(metadata, "broker_proposal_messages", e.ProposalMessage, ("id",))
ratings = entity_table(metadata, "broker_ratings", e.Rating, ("link_id",))
events = entity_table(metadata, "broker_events", e.BrokerEvent, ("id",))
