"""
RAGAS Evaluation Script
Evaluates the RAG pipeline on a test dataset.

Usage:
    python ragas_evaluate.py --test_file test_dataset.json --output results.json
"""

import json
import argparse
import asyncio
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
import textstat


def load_test_dataset(path: str) -> dict:
    """
    Expected format (JSON array):
    [
      {
        "question": "What does this letter require me to do?",
        "answer": "System-generated answer",
        "contexts": ["Retrieved passage 1", "Retrieved passage 2"],
        "ground_truth": "Expert-verified ground truth answer"
      }
    ]
    """
    with open(path) as f:
        data = json.load(f)
    return {
        "question": [d["question"] for d in data],
        "answer": [d["answer"] for d in data],
        "contexts": [d["contexts"] for d in data],
        "ground_truth": [d["ground_truth"] for d in data],
    }


def compute_readability(answers: list[str]) -> dict:
    scores = [textstat.flesch_reading_ease(a) for a in answers]
    grades = [textstat.flesch_kincaid_grade(a) for a in answers]
    return {
        "mean_flesch_reading_ease": round(sum(scores) / len(scores), 2),
        "mean_grade_level": round(sum(grades) / len(grades), 2),
        "plain_language_target_met": sum(1 for s in scores if s >= 60),
        "total_answers": len(answers),
    }


def run_ragas_evaluation(dataset_path: str, output_path: str):
    print(f"Loading test dataset from {dataset_path}")
    raw = load_test_dataset(dataset_path)
    dataset = Dataset.from_dict(raw)

    print("Running RAGAS evaluation...")
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )

    readability = compute_readability(raw["answer"])

    output = {
        "ragas_scores": {
            "faithfulness": round(result["faithfulness"], 4),
            "answer_relevancy": round(result["answer_relevancy"], 4),
            "context_precision": round(result["context_precision"], 4),
            "context_recall": round(result["context_recall"], 4),
        },
        "readability": readability,
        "targets": {
            "faithfulness_target": 0.85,
            "answer_relevancy_target": 0.80,
            "context_precision_target": 0.75,
            "context_recall_target": 0.80,
            "flesch_reading_ease_target": 60.0,
        },
        "targets_met": {
            "faithfulness": result["faithfulness"] >= 0.85,
            "answer_relevancy": result["answer_relevancy"] >= 0.80,
            "context_precision": result["context_precision"] >= 0.75,
            "context_recall": result["context_recall"] >= 0.80,
            "readability": readability["mean_flesch_reading_ease"] >= 60.0,
        }
    }

    print("\n=== RAGAS RESULTS ===")
    for metric, score in output["ragas_scores"].items():
        target = output["targets"][f"{metric}_target"]
        met = "✅" if output["targets_met"][metric] else "❌"
        print(f"  {met} {metric}: {score:.4f} (target: {target})")

    print("\n=== READABILITY ===")
    print(f"  Mean Flesch Reading Ease: {readability['mean_flesch_reading_ease']}")
    print(f"  Mean Grade Level: {readability['mean_grade_level']}")
    print(f"  Answers meeting plain-language target (≥60): {readability['plain_language_target_met']}/{readability['total_answers']}")

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test_file", default="test_dataset.json")
    parser.add_argument("--output", default="ragas_results.json")
    args = parser.parse_args()
    run_ragas_evaluation(args.test_file, args.output)
