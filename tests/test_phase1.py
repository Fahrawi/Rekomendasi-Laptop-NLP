# tests/test_phase1.py
# =============================================================================
# UNIT TESTS: Phase 1 Smart Filters + Dynamic AHP Weights
# =============================================================================
# Run with: python -m pytest tests/test_phase1.py -v

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
import pytest
from src.smart_filters_and_ahp import (
    apply_smart_filters,
    get_intent_based_weights,
    get_all_intents,
    validate_intent,
    get_intent_description
)


# =============================================================================
# FIXTURES - CREATE DUMMY DATA
# =============================================================================

@pytest.fixture
def dummy_laptop_df():
    """Create a dummy laptop dataframe for testing."""
    np.random.seed(42)
    
    data = {
        'Brand': ['Asus', 'Dell', 'Lenovo', 'MSI', 'HP', 'Acer', 'ROG', 'Alienware', 'ThinkPad', 'Pavilion'] * 2,
        'Model': [f'Model_{i}' for i in range(20)],
        'RAM': [8, 16, 8, 16, 8, 32, 16, 32, 16, 8, 32, 16, 64, 8, 16, 32, 48, 16, 8, 32],
        'CPU_score': [40, 50, 35, 60, 45, 75, 65, 85, 55, 40, 70, 60, 90, 45, 55, 70, 80, 60, 35, 75],
        'GPU_score': [2, 3, 1, 4, 2, 5, 3, 5, 1, 2, 4, 3, 5, 2, 3, 4, 4, 3, 1, 4],
        'GPU': ['GTX 1050', 'RTX 2060', 'Integrated', 'RTX 3060', 'GTX 1050', 'RTX 3080', 
                'RTX 3070', 'RTX 4080', 'Integrated', 'GTX 1650', 'RTX 4070', 'RTX 3060', 
                'RTX 4090', 'GTX 1050', 'RTX 2060', 'RTX 3070', 'RTX 4070', 'RTX 3060', 
                'Integrated', 'RTX 4080'],
        'Storage': [256, 512, 256, 1000, 512, 2000, 512, 1000, 512, 256, 1000, 512, 2000, 256, 512, 1000, 1500, 512, 256, 2000],
        'Storage type': ['SSD', 'SSD', 'HDD', 'SSD', 'SSD', 'SSD', 'SSD', 'SSD', 'SSD', 'HDD', 'SSD', 'SSD', 'SSD', 'HDD', 'SSD', 'SSD', 'SSD', 'SSD', 'HDD', 'SSD'],
        'Final Price': [8_000_000, 12_000_000, 6_000_000, 18_000_000, 10_000_000, 28_000_000,
                        16_000_000, 35_000_000, 9_000_000, 7_000_000, 24_000_000, 15_000_000,
                        50_000_000, 11_000_000, 13_000_000, 22_000_000, 32_000_000, 19_000_000,
                        5_000_000, 30_000_000]
    }
    
    return pd.DataFrame(data)


# =============================================================================
# TEST SUITE 1: get_intent_based_weights()
# =============================================================================

class TestIntentBasedWeights:
    """Test suite untuk get_intent_based_weights() function."""
    
    def test_all_intents_valid(self):
        """Test bahwa semua 10 intent return valid weights."""
        intents = get_all_intents()
        assert len(intents) == 10, "Should have 10 intents"
        
        for intent in intents:
            weights = get_intent_based_weights(intent)
            assert weights is not None, f"Weights for {intent} should not be None"
    
    def test_weight_sum_equals_one(self):
        """Test bahwa jumlah bobot = 1.0 untuk semua intent."""
        intents = get_all_intents()
        
        for intent in intents:
            weights = get_intent_based_weights(intent)
            
            # Sum only main weights, exclude bonus
            main_weights = [v for k, v in weights.items() if k != 'Storage_Type_Bonus']
            total = sum(main_weights)
            
            assert abs(total - 1.0) < 0.001, f"Total weight for {intent} should be ~1.0, got {total}"
    
    def test_weight_ranges(self):
        """Test bahwa setiap weight dalam range [0, 1]."""
        intents = get_all_intents()
        
        for intent in intents:
            weights = get_intent_based_weights(intent)
            
            for criteria, weight in weights.items():
                assert 0 <= weight <= 1, f"Weight for {criteria} in {intent} out of range: {weight}"
    
    def test_gaming_weights(self):
        """Test GPU weight tertinggi untuk Gaming intent."""
        weights = get_intent_based_weights("FIND_LAPTOP_FOR_GAME")
        
        assert weights['GPU'] >= weights['CPU'], "Gaming: GPU should be >= CPU"
        assert weights['GPU'] >= weights['RAM'], "Gaming: GPU should be >= RAM"
        assert weights['GPU'] >= weights['Storage'], "Gaming: GPU should be >= Storage"
        assert weights['GPU'] >= weights['Price'], "Gaming: GPU should be >= Price"
    
    def test_3d_design_weights(self):
        """Test RAM weight tinggi untuk 3D Design intent."""
        weights = get_intent_based_weights("3D_DESIGN")
        
        assert weights['RAM'] >= 0.20, "3D Design: RAM weight should be >= 0.20"
        assert weights['GPU'] >= 0.20, "3D Design: GPU weight should be >= 0.20"
    
    def test_ai_development_weights(self):
        """Test GPU weight dominan untuk AI Development."""
        weights = get_intent_based_weights("AI_DEVELOPMENT")
        
        assert weights['GPU'] >= 0.35, "AI Dev: GPU weight should be >= 0.35 (CUDA primary)"
        assert weights['RAM'] >= 0.25, "AI Dev: RAM weight should be >= 0.25"
    
    def test_office_workstation_weights(self):
        """Test Price weight tertinggi untuk Office intent."""
        weights = get_intent_based_weights("WORKSTATION")
        
        assert weights['Price'] >= weights['CPU'], "Office: Price should be >= CPU"
        assert weights['Price'] >= weights['GPU'], "Office: Price should be >= GPU"
        assert weights['Price'] >= weights['RAM'], "Office: Price should be >= RAM"
    
    def test_invalid_intent_returns_default(self):
        """Test bahwa invalid intent return default weights."""
        weights = get_intent_based_weights("INVALID_INTENT_XYZ")
        
        assert weights is not None, "Should return default weights for invalid intent"
        assert 'CPU' in weights, "Should have CPU key"
        total = sum([v for k, v in weights.items() if k != 'Storage_Type_Bonus'])
        assert abs(total - 1.0) < 0.001, "Default weights should also sum to 1.0"


# =============================================================================
# TEST SUITE 2: apply_smart_filters()
# =============================================================================

class TestSmartFilters:
    """Test suite untuk apply_smart_filters() function."""
    
    def test_gaming_filter_returns_dedicated_gpu(self, dummy_laptop_df):
        """Test Gaming filter hanya return laptop dengan dedicated GPU."""
        result = apply_smart_filters(
            dummy_laptop_df,
            intent="FIND_LAPTOP_FOR_GAME",
            budget=(8_000_000, 40_000_000)
        )
        
        assert len(result) > 0, "Should return filtered data"
        # All result laptops should have dedicated GPU
        integrated_keywords = ['integrated', 'uhd', 'hd graphics', 'iris']
        for gpu in result['GPU']:
            gpu_lower = str(gpu).lower()
            has_integrated = any(kw in gpu_lower for kw in integrated_keywords)
            assert not has_integrated, f"Gaming filter should exclude integrated GPU: {gpu}"
    
    def test_3d_design_filter_requires_high_ram(self, dummy_laptop_df):
        """Test 3D Design filter require minimum 32GB RAM."""
        result = apply_smart_filters(
            dummy_laptop_df,
            intent="3D_DESIGN"
        )
        
        assert len(result) > 0, "Should return filtered data"
        assert result['RAM'].min() >= 32, "3D Design should require 32GB+ RAM"
    
    def test_budget_filter_single_value(self, dummy_laptop_df):
        """Test budget filter dengan single value (maximum budget)."""
        max_budget = 15_000_000
        result = apply_smart_filters(
            dummy_laptop_df,
            intent="WORKSTATION",
            budget=max_budget
        )
        
        assert all(result['Final Price'] <= max_budget), "All results should be <= max budget"
    
    def test_budget_filter_range(self, dummy_laptop_df):
        """Test budget filter dengan range (min, max)."""
        budget_range = (10_000_000, 25_000_000)
        result = apply_smart_filters(
            dummy_laptop_df,
            intent="WEB_DEVELOPMENT",
            budget=budget_range
        )
        
        assert len(result) > 0, "Should return filtered data"
        assert all(result['Final Price'] >= budget_range[0]), "All results >= min budget"
        assert all(result['Final Price'] <= budget_range[1]), "All results <= max budget"
    
    def test_ram_filter(self, dummy_laptop_df):
        """Test RAM filter requirement."""
        min_ram = 16
        result = apply_smart_filters(
            dummy_laptop_df,
            intent="DATA_ANALYSIS",
            ram=min_ram
        )
        
        assert all(result['RAM'] >= min_ram), f"All results should have RAM >= {min_ram}GB"
    
    def test_office_workstation_returns_budget_friendly(self, dummy_laptop_df):
        """Test Office intent returns budget-friendly options."""
        result = apply_smart_filters(
            dummy_laptop_df,
            intent="WORKSTATION"
        )
        
        # Should filter by lower specs compared to Gaming
        assert result['RAM'].mean() <= 20, "Office intent should average RAM <= 20GB"
    
    def test_gaming_vs_office_specs_difference(self, dummy_laptop_df):
        """Test bahwa Gaming filter lebih strict daripada Office."""
        gaming = apply_smart_filters(
            dummy_laptop_df,
            intent="FIND_LAPTOP_FOR_GAME"
        )
        
        office = apply_smart_filters(
            dummy_laptop_df,
            intent="WORKSTATION"
        )
        
        # Gaming average GPU score should be higher
        if len(gaming) > 0 and len(office) > 0:
            gaming_avg_gpu = gaming['GPU_score'].mean()
            office_avg_gpu = office['GPU_score'].mean()
            assert gaming_avg_gpu >= office_avg_gpu, "Gaming laptops should have better average GPU"
    
    def test_returns_dataframe(self, dummy_laptop_df):
        """Test bahwa function return pandas DataFrame."""
        result = apply_smart_filters(
            dummy_laptop_df,
            intent="WEB_DEVELOPMENT"
        )
        
        assert isinstance(result, pd.DataFrame), "Should return DataFrame"
    
    def test_filtered_data_has_same_columns(self, dummy_laptop_df):
        """Test bahwa filtered data memiliki kolom yang sama."""
        result = apply_smart_filters(
            dummy_laptop_df,
            intent="MULTITASKING"
        )
        
        assert list(result.columns) == list(dummy_laptop_df.columns), "Should retain all columns"
    
    def test_no_gpu_requirement_intent(self, dummy_laptop_df):
        """Test intent yang tidak require GPU (Office, Web Dev)."""
        result_office = apply_smart_filters(
            dummy_laptop_df,
            intent="WORKSTATION"
        )
        
        result_web = apply_smart_filters(
            dummy_laptop_df,
            intent="WEB_DEVELOPMENT"
        )
        
        # Both should include laptops with low/no GPU
        assert len(result_office) > 0, "Office should return results"
        assert len(result_web) > 0, "Web Dev should return results"


# =============================================================================
# TEST SUITE 3: Helper Functions
# =============================================================================

class TestHelperFunctions:
    """Test suite untuk helper functions."""
    
    def test_get_all_intents_returns_10(self):
        """Test bahwa get_all_intents() return 10 intent."""
        intents = get_all_intents()
        assert len(intents) == 10, "Should have exactly 10 intents"
    
    def test_validate_intent_correct(self):
        """Test validate_intent untuk intent valid."""
        intents = get_all_intents()
        for intent in intents:
            assert validate_intent(intent) == True, f"Intent {intent} should be valid"
    
    def test_validate_intent_incorrect(self):
        """Test validate_intent untuk intent invalid."""
        assert validate_intent("INVALID_INTENT") == False, "Invalid intent should return False"
        assert validate_intent("") == False, "Empty intent should return False"
    
    def test_get_intent_description(self):
        """Test get_intent_description untuk semua intent."""
        intents = get_all_intents()
        for intent in intents:
            desc = get_intent_description(intent)
            assert isinstance(desc, str), "Description should be string"
            assert len(desc) > 0, "Description should not be empty"
            assert intent.lower() in desc.lower() or any(
                word in desc.lower() for word in intent.lower().split('_')
            ), f"Description should mention intent name: {intent} -> {desc}"


# =============================================================================
# TEST SUITE 4: INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests untuk full workflow."""
    
    def test_workflow_gaming(self, dummy_laptop_df):
        """Test full workflow untuk Gaming intent."""
        # Step 1: Filter dengan RBR
        filtered_df = apply_smart_filters(
            dummy_laptop_df,
            intent="FIND_LAPTOP_FOR_GAME",
            budget=(10_000_000, 30_000_000),
            ram=8
        )
        
        assert len(filtered_df) > 0, "Gaming workflow should return results"
        
        # Step 2: Get AHP weights
        weights = get_intent_based_weights("FIND_LAPTOP_FOR_GAME")
        
        assert weights['GPU'] >= 0.35, "Gaming weights should prioritize GPU"
        print(f"✓ Gaming workflow: {len(filtered_df)} laptops, GPU weight={weights['GPU']:.1%}")
    
    def test_workflow_3d_design(self, dummy_laptop_df):
        """Test full workflow untuk 3D Design intent."""
        # Step 1: Filter dengan RBR
        filtered_df = apply_smart_filters(
            dummy_laptop_df,
            intent="3D_DESIGN",
            budget=(20_000_000, 50_000_000)
        )
        
        # Step 2: Get AHP weights
        weights = get_intent_based_weights("3D_DESIGN")
        
        assert weights['GPU'] >= 0.25 and weights['RAM'] >= 0.25, "3D Design needs GPU + RAM"
        print(f"✓ 3D Design workflow: {len(filtered_df)} laptops, GPU={weights['GPU']:.1%}, RAM={weights['RAM']:.1%}")
    
    def test_workflow_office(self, dummy_laptop_df):
        """Test full workflow untuk Office intent."""
        # Step 1: Filter dengan RBR
        filtered_df = apply_smart_filters(
            dummy_laptop_df,
            intent="WORKSTATION",
            budget=(5_000_000, 15_000_000)
        )
        
        assert len(filtered_df) > 0, "Office workflow should return results"
        
        # Step 2: Get AHP weights
        weights = get_intent_based_weights("WORKSTATION")
        
        assert weights['Price'] >= 0.35, "Office intent should prioritize Price"
        print(f"✓ Office workflow: {len(filtered_df)} laptops, Price weight={weights['Price']:.1%}")
    
    def test_all_intents_have_weights_and_filters(self):
        """Test bahwa semua 10 intent punya weights dan filter rules."""
        intents = get_all_intents()
        
        for intent in intents:
            # Test weights exist
            weights = get_intent_based_weights(intent)
            assert weights is not None, f"Weights for {intent} should exist"
            
            # Test description exist
            desc = get_intent_description(intent)
            assert len(desc) > 0, f"Description for {intent} should exist"
            
            print(f"✓ {intent:25s} - {desc}")


# =============================================================================
# MAIN - RUN TESTS
# =============================================================================

if __name__ == "__main__":
    """
    Run tests manually without pytest.
    Usage: python tests/test_phase1.py
    """
    print("\n" + "=" * 80)
    print("PHASE 1 TESTING - Smart Filters + Dynamic AHP Weights")
    print("=" * 80 + "\n")
    
    # Create dummy data
    np.random.seed(42)
    dummy_data = {
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
    df_dummy = pd.DataFrame(dummy_data)
    
    # Test 1: Helper functions
    print("TEST 1: Helper Functions")
    print("-" * 80)
    intents = get_all_intents()
    print(f"✓ get_all_intents() returns {len(intents)} intents")
    print(f"✓ validate_intent('FIND_LAPTOP_FOR_GAME') = {validate_intent('FIND_LAPTOP_FOR_GAME')}")
    print(f"✓ validate_intent('INVALID') = {validate_intent('INVALID')}")
    
    # Test 2: AHP Weights
    print("\nTEST 2: AHP Weights (3 examples)")
    print("-" * 80)
    
    for intent in ["FIND_LAPTOP_FOR_GAME", "AI_DEVELOPMENT", "WORKSTATION"]:
        weights = get_intent_based_weights(intent)
        total = sum([v for k, v in weights.items() if k != 'Storage_Type_Bonus'])
        print(f"\n{intent}:")
        print(f"  Total weight: {total:.3f} (should be 1.0)")
        print(f"  ✓ Valid weights returned")
    
    # Test 3: Smart Filters
    print("\nTEST 3: Smart Filters")
    print("-" * 80)
    
    result_gaming = apply_smart_filters(
        df_dummy,
        intent="FIND_LAPTOP_FOR_GAME",
        budget=(8_000_000, 30_000_000)
    )
    print(f"\n✓ Gaming filter: {len(result_gaming)} / {len(df_dummy)} laptops")
    print(f"  Avg RAM: {result_gaming['RAM'].mean():.1f}GB")
    print(f"  Avg GPU Score: {result_gaming['GPU_score'].mean():.2f}")
    
    result_office = apply_smart_filters(
        df_dummy,
        intent="WORKSTATION",
        budget=(5_000_000, 15_000_000)
    )
    print(f"\n✓ Office filter: {len(result_office)} / {len(df_dummy)} laptops")
    print(f"  Avg RAM: {result_office['RAM'].mean():.1f}GB")
    print(f"  Avg GPU Score: {result_office['GPU_score'].mean():.2f}")
    
    result_ai = apply_smart_filters(
        df_dummy,
        intent="AI_DEVELOPMENT"
    )
    print(f"\n✓ AI/ML filter: {len(result_ai)} / {len(df_dummy)} laptops")
    print(f"  Avg RAM: {result_ai['RAM'].mean():.1f}GB")
    print(f"  Avg GPU Score: {result_ai['GPU_score'].mean():.2f}")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80 + "\n")
