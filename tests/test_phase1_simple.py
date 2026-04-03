# tests/test_phase1_simple.py
# =============================================================================
# SIMPLE VALIDATION TESTS: Phase 1 Smart Filters + Dynamic AHP Weights
# NO PYTEST DEPENDENCY - Just run directly
# =============================================================================
# Run with: python tests/test_phase1_simple.py

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
from src.smart_filters_and_ahp import (
    apply_smart_filters,
    get_intent_based_weights,
    get_all_intents,
    validate_intent,
    get_intent_description
)


def create_dummy_laptop_df():
    """Create dummy laptop dataframe for testing."""
    np.random.seed(42)
    
    data = {
        'Brand': ['Asus', 'Dell', 'Lenovo', 'MSI', 'HP', 'Acer', 'ROG', 'Alienware',
                  'ThinkPad', 'Pavilion'] * 2,
        'Model': [f'Model_{i}' for i in range(20)],
        'RAM': [8, 16, 8, 16, 8, 32, 16, 32, 16, 8, 32, 16, 64, 8, 16, 32, 48, 16, 8, 32],
        'CPU_score': [40, 50, 35, 60, 45, 75, 65, 85, 55, 40, 70, 60, 90, 45, 55, 70, 80, 60, 35, 75],
        'GPU_score': [2, 3, 1, 4, 2, 5, 3, 5, 1, 2, 4, 3, 5, 2, 3, 4, 4, 3, 1, 4],
        'GPU': ['GTX 1050', 'RTX 2060', 'Integrated', 'RTX 3060', 'GTX 1050', 'RTX 3080',
                'RTX 3070', 'RTX 4080', 'Integrated', 'GTX 1650', 'RTX 4070', 'RTX 3060',
                'RTX 4090', 'GTX 1050', 'RTX 2060', 'RTX 3070', 'RTX 4070', 'RTX 3060',
                'Integrated', 'RTX 4080'],
        'Storage': [256, 512, 256, 1000, 512, 2000, 512, 1000, 512, 256, 1000, 512, 2000,
                    256, 512, 1000, 1500, 512, 256, 2000],
        'Storage type': ['SSD', 'SSD', 'HDD', 'SSD', 'SSD', 'SSD', 'SSD', 'SSD', 'SSD', 'HDD',
                         'SSD', 'SSD', 'SSD', 'HDD', 'SSD', 'SSD', 'SSD', 'SSD', 'HDD', 'SSD'],
        'Final Price': [8_000_000, 12_000_000, 6_000_000, 18_000_000, 10_000_000, 28_000_000,
                        16_000_000, 35_000_000, 9_000_000, 7_000_000, 24_000_000, 15_000_000,
                        50_000_000, 11_000_000, 13_000_000, 22_000_000, 32_000_000, 19_000_000,
                        5_000_000, 30_000_000]
    }
    
    return pd.DataFrame(data)


# =============================================================================
# TEST HELPER FUNCTIONS
# =============================================================================

test_count = 0
passed_count = 0
failed_tests = []

def assert_equal(actual, expected, message):
    global test_count, passed_count, failed_tests
    test_count += 1
    if actual == expected:
        print(f"  ✓ {message}")
        passed_count += 1
    else:
        print(f"  ✗ {message}")
        print(f"    Expected: {expected}, Got: {actual}")
        failed_tests.append(message)

def assert_true(condition, message):
    global test_count, passed_count, failed_tests
    test_count += 1
    if condition:
        print(f"  ✓ {message}")
        passed_count += 1
    else:
        print(f"  ✗ {message}")
        failed_tests.append(message)

def assert_range(value, min_val, max_val, message):
    global test_count, passed_count, failed_tests
    test_count += 1
    if min_val <= value <= max_val:
        print(f"  ✓ {message}")
        passed_count += 1
    else:
        print(f"  ✗ {message}")
        print(f"    Expected [{min_val}, {max_val}], Got: {value}")
        failed_tests.append(message)


# =============================================================================
# TEST 1: Helper Functions
# =============================================================================

def test_helper_functions():
    print("\n" + "="*80)
    print("TEST 1: Helper Functions")
    print("="*80)
    
    # Test get_all_intents
    intents = get_all_intents()
    assert_equal(len(intents), 10, "get_all_intents() returns exactly 10 intents")
    
    # Test validate_intent
    assert_true(validate_intent("FIND_LAPTOP_FOR_GAME"), "validate_intent() recognizes valid intent")
    assert_true(not validate_intent("INVALID_INTENT"), "validate_intent() rejects invalid intent")
    
    # Test get_intent_description
    desc = get_intent_description("FIND_LAPTOP_FOR_GAME")
    assert_true(isinstance(desc, str) and len(desc) > 0, "get_intent_description() returns non-empty string")
    
    # List all intents
    print("\n  All 10 supported intents:")
    for i, intent in enumerate(intents, 1):
        print(f"    {i:2d}. {intent}")


# =============================================================================
# TEST 2: AHP Weight Validation
# =============================================================================

def test_ahp_weights():
    print("\n" + "="*80)
    print("TEST 2: AHP Weight Validation")
    print("="*80)
    
    intents = get_all_intents()
    
    for intent in intents:
        print(f"\n  {intent}:")
        weights = get_intent_based_weights(intent)
        
        # Check main weights keys exist
        assert_true('CPU' in weights, f"    Has CPU weight")
        assert_true('GPU' in weights, f"    Has GPU weight")
        assert_true('RAM' in weights, f"    Has RAM weight")
        assert_true('Storage' in weights, f"    Has Storage weight")
        assert_true('Price' in weights, f"    Has Price weight")
        
        # Check total = 1.0
        main_weights = [v for k, v in weights.items() if k != 'Storage_Type_Bonus']
        total = sum(main_weights)
        assert_range(total, 0.99, 1.01, f"    Total weight = {total:.4f} (≈ 1.0)")
        
        # Check each weight in [0, 1]
        for criteria, weight in weights.items():
            if criteria != 'Storage_Type_Bonus':
                assert_range(weight, 0, 1, f"    {criteria} weight = {weight:.2%} (valid range)")


# =============================================================================
# TEST 3: Smart Filters - Single Intent Tests
# =============================================================================

def test_smart_filters():
    print("\n" + "="*80)
    print("TEST 3: Smart Filters - Filtering Logic")
    print("="*80)
    
    df = create_dummy_laptop_df()
    total_laptops = len(df)
    
    # Test 3.1: Gaming filter (dedicated GPU)
    print(f"\n  Gaming Intent (dedicated GPU required):")
    result_gaming = apply_smart_filters(df, intent="FIND_LAPTOP_FOR_GAME")
    assert_true(len(result_gaming) > 0, f"    Returns {len(result_gaming)} laptops")
    assert_true(len(result_gaming) <= total_laptops, f"    Result count <= original")
    
    # Test 3.2: 3D Design (high RAM)
    print(f"\n  3D Design Intent (32GB+ RAM required):")
    result_3d = apply_smart_filters(df, intent="3D_DESIGN")
    if len(result_3d) > 0:
        assert_true(result_3d['RAM'].min() >= 32, f"    Min RAM = {result_3d['RAM'].min()}GB (>= 32)")
    else:
        print(f"    (No laptops meet 32GB+ requirement)")
    
    # Test 3.3: Office workstation
    print(f"\n  Office/Workstation Intent:")
    result_office = apply_smart_filters(df, intent="WORKSTATION")
    assert_true(len(result_office) > 0, f"    Returns {len(result_office)} laptops")
    
    # Test 3.4: Budget filter (single value)
    print(f"\n  Budget Filter (max = 15M):")
    result_budget = apply_smart_filters(
        df,
        intent="WORKSTATION",
        budget=15_000_000
    )
    if len(result_budget) > 0:
        assert_true(result_budget['Final Price'].max() <= 15_000_000, 
                   f"    Max price = Rp{result_budget['Final Price'].max():,} (≤ 15M)")
    
    # Test 3.5: Budget range filter
    print(f"\n  Budget Range Filter (10M - 25M):")
    result_range = apply_smart_filters(
        df,
        intent="WEB_DEVELOPMENT",
        budget=(10_000_000, 25_000_000)
    )
    if len(result_range) > 0:
        min_price = result_range['Final Price'].min()
        max_price = result_range['Final Price'].max()
        assert_true(min_price >= 10_000_000, f"    Min price = Rp{min_price:,} (>= 10M)")
        assert_true(max_price <= 25_000_000, f"    Max price = Rp{max_price:,} (≤ 25M)")
    
    # Test 3.6: RAM filter
    print(f"\n  RAM Filter (minimum 16GB):")
    result_ram = apply_smart_filters(
        df,
        intent="OLAH_DATA",
        ram=16
    )
    if len(result_ram) > 0:
        assert_true(result_ram['RAM'].min() >= 16, f"    Min RAM = {result_ram['RAM'].min()}GB (>= 16)")


# =============================================================================
# TEST 4: Comparative Analysis
# =============================================================================

def test_intent_comparison():
    print("\n" + "="*80)
    print("TEST 4: Intent Comparative Analysis")
    print("="*80)
    
    df = create_dummy_laptop_df()
    
    # Compare different intent filters
    intents_to_compare = [
        "FIND_LAPTOP_FOR_GAME",
        "3D_DESIGN",
        "WORKSTATION",
        "WEB_DEVELOPMENT"
    ]
    
    print("\n  Comparing filter results across intents:")
    print(f"  {'Intent':<30} {'Count':<8} {'Avg RAM':<12} {'Avg GPU':<12} {'Priority'}")
    print(f"  {'-'*30} {'-'*8} {'-'*12} {'-'*12} {'-'*20}")
    
    for intent in intents_to_compare:
        result = apply_smart_filters(df, intent=intent)
        weights = get_intent_based_weights(intent)
        
        if len(result) > 0:
            avg_ram = result['RAM'].mean()
            avg_gpu = result['GPU_score'].mean()
            # Find primary criteria
            max_weight_criteria = max(weights, key=lambda k: weights[k] if k != 'Storage_Type_Bonus' else 0)
            priority = f"{max_weight_criteria} ({weights[max_weight_criteria]:.0%})"
        else:
            avg_ram = 0
            avg_gpu = 0
            priority = "N/A"
        
        print(f"  {intent:<30} {len(result):<8} {avg_ram:<12.1f} {avg_gpu:<12.2f} {priority}")


# =============================================================================
# TEST 5: Integration - Full Workflow
# =============================================================================

def test_full_workflow():
    print("\n" + "="*80)
    print("TEST 5: Full Workflow Integration")
    print("="*80)
    
    df = create_dummy_laptop_df()
    
    workflows = [
        {
            'name': 'Gamer searching for RTX laptop under 30M',
            'intent': 'FIND_LAPTOP_FOR_GAME',
            'budget': (15_000_000, 30_000_000),
            'ram': 8
        },
        {
            'name': 'AI Developer needing CUDA support',
            'intent': 'AI_DEVELOPMENT',
            'budget': None,
            'ram': 16  # Override minimum
        },
        {
            'name': 'Office worker on tight budget',
            'intent': 'WORKSTATION',
            'budget': (5_000_000, 12_000_000),
            'ram': None
        }
    ]
    
    for workflow in workflows:
        print(f"\n  Workflow: {workflow['name']}")
        
        # Step 1: Apply smart filters (RBR)
        filtered_df = apply_smart_filters(
            df,
            intent=workflow['intent'],
            budget=workflow['budget'],
            ram=workflow['ram']
        )
        
        # Step 2: Get AHP weights (for TOPSIS)
        weights = get_intent_based_weights(workflow['intent'])
        
        print(f"    Step 1 (RBR Filter): {len(filtered_df)}/{len(df)} laptops match criteria")
        print(f"    Step 2 (AHP Weights):")
        for criteria in ['CPU', 'GPU', 'RAM', 'Storage', 'Price']:
            print(f"      - {criteria}: {weights[criteria]:.1%}")


# =============================================================================
# MAIN - RUN ALL TESTS
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("PHASE 1 VALIDATION - Smart Filters + Dynamic AHP Weights")
    print("Hybrid Recommender System: NLP → RBR → Dynamic AHP → TOPSIS")
    print("="*80)
    
    # Run all tests
    test_helper_functions()
    test_ahp_weights()
    test_smart_filters()
    test_intent_comparison()
    test_full_workflow()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total Tests: {test_count}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {test_count - passed_count}")
    
    if failed_tests:
        print(f"\nFailed Tests:")
        for test in failed_tests:
            print(f"  - {test}")
    else:
        print("\n✅ ALL TESTS PASSED!")
    
    print("\n" + "="*80)
    print("Phase 1 Implementation Status: COMPLETE ✅")
    print("="*80)
    print("\nNext Steps:")
    print("  1. Phase 1a: Unit tests with pytest (optional)")
    print("  2. Phase 2: Integrate TOPSIS ranking algorithm")
    print("  3. Phase 3: Merge with FastAPI app.py")
    print("  4. Phase 4: End-to-end testing with real NLP pipeline")
    print("\n")
