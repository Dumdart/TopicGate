"""Framework-independent presentation models and formatting rules."""

from topicgate.presentation.topic_presentation import (
    BrokerDisplaySummary,
    SubscriptionDetail,
    TopicDetail,
    TopicTreeNode,
    broker_display_summary,
    build_topic_tree,
    collect_visible_topic_paths,
    matching_subscription,
    subscription_detail,
    topic_detail,
)
from topicgate.presentation.snapshot_presentation import (
    BrokerSnapshotHealth,
    SnapshotQuery,
    TopicStateBadge,
    snapshot_health,
    topic_state_badges,
)

__all__ = [
    "BrokerDisplaySummary",
    "BrokerSnapshotHealth",
    "SnapshotQuery",
    "SubscriptionDetail",
    "TopicDetail",
    "TopicTreeNode",
    "TopicStateBadge",
    "broker_display_summary",
    "build_topic_tree",
    "collect_visible_topic_paths",
    "matching_subscription",
    "subscription_detail",
    "snapshot_health",
    "topic_state_badges",
    "topic_detail",
]
