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

__all__ = [
    "BrokerDisplaySummary",
    "SubscriptionDetail",
    "TopicDetail",
    "TopicTreeNode",
    "broker_display_summary",
    "build_topic_tree",
    "collect_visible_topic_paths",
    "matching_subscription",
    "subscription_detail",
    "topic_detail",
]
