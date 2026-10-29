from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    appeals,
    assignments,
    audit,
    auth,
    courses,
    datasets,
    grades,
    learners,
    resubmissions,
    submissions,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(courses.router)
api_router.include_router(learners.router)
api_router.include_router(assignments.router)
api_router.include_router(submissions.router)
api_router.include_router(grades.router)
api_router.include_router(resubmissions.router)
api_router.include_router(appeals.router)
api_router.include_router(audit.router)
api_router.include_router(analytics.router)
api_router.include_router(datasets.router)
