"""Pydantic models for the Signals Activation Protocol."""

from typing import List, Optional, Dict, Any, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# --- Core Protocol Models ---

class PlatformDeployment(BaseModel):
    """Single platform deployment information."""
    platform: str
    account: Optional[str] = None
    is_live: bool
    scope: Literal["platform-wide", "account-specific"]
    decisioning_platform_segment_id: Optional[str] = None
    estimated_activation_duration_minutes: Optional[int] = None


class PricingModel(BaseModel):
    """Pricing information for a signal."""
    cpm: Optional[float] = None
    revenue_share_percentage: Optional[float] = None
    currency: str = "USD"


class SignalResponse(BaseModel):
    """Single signal in get_signals response."""
    signals_agent_segment_id: str
    name: str
    description: str
    signal_type: Union[Literal["private", "marketplace", "audience", "bidding", "contextual", "geographical", "temporal", "environmental"], str]
    data_provider: str
    coverage_percentage: Optional[float] = None
    deployments: List[PlatformDeployment]
    pricing: PricingModel
    has_coverage_data: Optional[bool] = None
    has_pricing_data: Optional[bool] = None


# --- Request Models ---

class PlatformSpecification(BaseModel):
    """Specification for a single platform to deliver to."""
    platform: str = Field(
        ..., 
        description="Platform identifier (e.g., 'the-trade-desk', 'index-exchange', 'google-dv360')",
        examples=["the-trade-desk", "index-exchange"]
    )
    account: Optional[str] = Field(
        None,
        description="Optional account ID for platform-specific delivery. Required for some platforms.",
        examples=["1489997", "acct_12345"]
    )


class DeliverySpecification(BaseModel):
    """Specifies where signals should be delivered/discovered."""
    platforms: Union[List[PlatformSpecification], Literal["all"]] = Field(
        ...,
        description='Either "all" to search all platforms, or a list of specific platform specifications',
        examples=[
            "all",
            [{"platform": "the-trade-desk"}, {"platform": "index-exchange", "account": "1489997"}]
        ]
    )
    countries: List[str] = Field(
        ["US"],
        description="List of country codes for geographic targeting",
        examples=[["US"], ["US", "UK", "CA"]]
    )


class SignalFilters(BaseModel):
    """Filters for signal discovery."""
    catalog_types: Optional[List[Literal["private", "marketplace"]]] = None
    data_providers: Optional[List[str]] = None
    max_cpm: Optional[float] = None
    min_coverage_percentage: Optional[float] = None


class GetSignalsRequest(BaseModel):
    """Request for discovering signals matching your targeting needs."""
    signal_spec: str = Field(
        ...,
        description="Natural language description of your target signals",
        examples=[
            "luxury car buyers in California",
            "parents with young children interested in educational content",
            "high-income travelers who book premium hotels"
        ]
    )
    deliver_to: DeliverySpecification = Field(
        ...,
        description="Where to search for/deliver signals"
    )
    filters: Optional[SignalFilters] = Field(
        None,
        description="Optional filters to refine results"
    )
    max_results: Optional[int] = Field(
        10,
        description="Maximum number of signals to return",
        ge=1,
        le=100
    )
    principal_id: Optional[str] = Field(
        None,
        description="Your principal/account ID for accessing private catalogs and custom pricing",
        examples=["acme_corp", "agency_123"]
    )


class CustomSegmentProposal(BaseModel):
    """AI-generated custom segment proposal."""
    proposed_name: str
    description: str
    target_signals: str
    estimated_coverage_percentage: float
    estimated_cpm: float
    creation_rationale: str
    custom_segment_id: Optional[str] = None  # ID for activation


class GetSignalsResponse(BaseModel):
    """Response from get_signals."""
    signals: List[SignalResponse]
    custom_segment_proposals: Optional[List[CustomSegmentProposal]] = None


class ActivateSignalRequest(BaseModel):
    """Request to activate a signal."""
    signals_agent_segment_id: str
    platform: str
    account: Optional[str] = None


class ActivateSignalResponse(BaseModel):
    """Response from activate_signal."""
    decisioning_platform_segment_id: str
    estimated_activation_duration_minutes: int
    status: Literal["deployed", "activating", "failed"] = "activating"
    deployed_at: Optional[datetime] = None
    error_message: Optional[str] = None





# --- Database Models ---

class SignalSegment(BaseModel):
    """Internal signal segment model."""
    id: str
    name: str
    description: str
    data_provider: str
    coverage_percentage: float
    signal_type: Union[Literal["private", "marketplace", "audience", "bidding", "contextual", "geographical", "temporal", "environmental"], str]
    catalog_access: Literal["public", "personalized", "private"]
    base_cpm: float
    revenue_share_percentage: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class PlatformDeploymentRecord(BaseModel):
    """Database record for platform deployments."""
    signals_agent_segment_id: str
    platform: str
    account: Optional[str] = None
    decisioning_platform_segment_id: Optional[str] = None
    scope: Literal["platform-wide", "account-specific"]
    is_live: bool
    deployed_at: Optional[datetime] = None
    estimated_activation_duration_minutes: int = 60


# --- Error Models ---

class SignalError(BaseModel):
    """Error response model."""
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None


# Error codes as defined in the specification
SIGNALS_AGENT_SEGMENT_NOT_FOUND = "SIGNALS_AGENT_SEGMENT_NOT_FOUND"
ACTIVATION_FAILED = "ACTIVATION_FAILED"
ALREADY_ACTIVATED = "ALREADY_ACTIVATED"
DEPLOYMENT_UNAUTHORIZED = "DEPLOYMENT_UNAUTHORIZED"
INVALID_PRICING_MODEL = "INVALID_PRICING_MODEL"
AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
AGENT_ACCESS_DENIED = "AGENT_ACCESS_DENIED"