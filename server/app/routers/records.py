from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import schemas, crud, database
from app.utils.openai_client import summarize_text, generate_title, extract_keywords, generate_image

router = APIRouter()


@router.get("/", response_model=List[schemas.Record])
def get_all_records(db: Session = Depends(database.get_db)):
    """
    Retrieve all records.
    """
    records = db.query(models.Record).all()
    if not records:
        raise HTTPException(status_code=404, detail="No records found")
    return records


@router.get("/user/{elder_id}", response_model=List[schemas.Record])
def get_records_for_elder(elder_id: int, db: Session = Depends(database.get_db)):
    """
    Retrieve all records for a specific elder by elder_id.
    """
    elder = crud.get_elder_by_id(db, elder_id=elder_id)
    if not elder:
        raise HTTPException(status_code=404, detail="Elder not found")

    records = crud.get_records_by_elder_id(db, elder_id=elder_id)
    if not records:
        raise HTTPException(status_code=404, detail="No records found for this elder")
    return records


@router.get("/{record_id}", response_model=schemas.Record)
def get_record_by_id(record_id: int, db: Session = Depends(database.get_db)):
    """
    Retrieve a single record by its ID.
    """
    record = crud.get_record_by_id(db, record_id=record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.post("/", response_model=schemas.Record)
def create_todays_record(
    elder_id: int,
    question_ids: List[int],
    db: Session = Depends(database.get_db)
):
    """
    Create today's record for an elder, including title, summary, keywords, and images.
    """
    # Validate elder
    elder = crud.get_elder_by_id(db, elder_id=elder_id)
    if not elder:
        raise HTTPException(status_code=404, detail="Elder not found")

    # Validate questions and retrieve answers
    answers = crud.get_answers_by_question_ids(db, elder_id=elder_id, question_ids=question_ids)
    if not answers:
        raise HTTPException(status_code=404, detail="No answers found for the provided questions")

    # Combine answers into a single text
    combined_text = "\n".join([answer.response for answer in answers])

    # Use OpenAI to generate content
    summary = summarize_text(combined_text)
    title = generate_title(summary)
    keywords = extract_keywords(summary)
    image_url = generate_image(", ".join(keywords))

    # Create the record
    record_data = schemas.RecordCreate(
        title=title,
        content=summary,
        elder_id=elder_id,
    )
    new_record = crud.create_record(db, record=record_data)

    # Add keywords and image to the record
    for keyword in keywords:
        keyword_instance = crud.create_or_get_keyword(db, keyword=keyword)
        crud.add_keyword_to_record(db, record_id=new_record.id, keyword_id=keyword_instance.id)

    crud.add_image_to_record(db, record_id=new_record.id, image_url=image_url)

    return new_record