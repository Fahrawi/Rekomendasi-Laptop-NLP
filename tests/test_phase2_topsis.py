# tests/test_phase2_topsis.py
# =============================================================================
# PHASE 2 TEST SUITE: TOPSIS RANKING ENGINE
# =============================================================================
#
# Test Coverage:
# - TOPSIS algorithm correctness
# - Score normalization (0-1 range)
# - Ranking order verification
# - Criteria handling (benefit vs cost)
# - Edge cases and data validation
# - Integration with Phase 1 outputs
#
# Run: python tests/test_phase2_topsis.py
# =============================================================================

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from topsis_engine import run_topsis, get_topsis_summary, define_default_criteria


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================

def create_simple_test_data():
    """Create simple test data with known expected rankings."""
    return pd.DataFrame({
        'Brand': ['A', 'B', 'C'],
        'Model': ['M1', 'M2', 'M3'],
        'CPU_score': [100, 50, 75],      # Higher = Better
        'GPU_score': [4, 2, 3],           # Higher = Better
        'RAM': [32, 8, 16],               # Higher = Better
        'Storage': [1000, 256, 512],      # Higher = Better
        'Final Price': [10_000_000, 5_000_000, 8_000_000]  # Lower = Better
    })


def create_gaming_test_data():
    """Create gaming-focused test data (high GPU priority)."""
    return pd.DataFrame({
        'Brand': ['ASUS ROG', 'MSI', 'Lenovo Legion', 'Acer', 'Dell Alienware'],
        'Model': ['G14', 'GE76', 'Legion 5', 'Nitro', 'M17'],
        'CPU_score': [80, 85, 75, 70, 90],
        'GPU_score': [5, 5, 4, 4, 5],
        'RAM': [16, 16, 16, 8, 32],
        'Storage': [512, 1000, 512, 256, 1000],
        'Final Price': [25_000_000, 28_000_000, 20_000_000, 15_000_000, 35_000_000]
    })


def create_workstation_test_data():
    """Create workstation test data (focus on RAM and CPU)."""
    return pd.DataFrame({
        'Brand': ['HP', 'Lenovo', 'Dell', 'ASUS'],
        'Model': ['ZBook', 'ThinkPad', 'Precision', 'ProBook'],
        'CPU_score': [90, 85, 95, 80],
        'GPU_score': [3, 2, 4, 2],
        'RAM': [64, 32, 64, 32],
        'Storage': [1000, 512, 1000, 512],
        'Final Price': [50_000_000, 35_000_000, 55_000_000, 40_000_000]
    })


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

class TestTOPSISEngine:
    """Test suite for TOPSIS ranking engine."""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []
    
    def assert_true(self, condition, message):
        """Assert that condition is True."""
        if condition:
            self.tests_passed += 1
            self.test_results.append(f"[PASS] {message}")
        else:
            self.tests_failed += 1
            self.test_results.append(f"[FAIL] {message}")
        return condition
    
    def assert_equal(self, actual, expected, message, tolerance=0.0001):
        """Assert that actual approximately equals expected."""
        if isinstance(expected, (int, float)):
            if abs(actual - expected) <= tolerance:
                self.tests_passed += 1
                self.test_results.append(f"[PASS] {message}")
                return True
            else:
                self.tests_failed += 1
                self.test_results.append(f"[FAIL] {message} (expected {expected}, got {actual})")
                return False
        else:
            if actual == expected:
                self.tests_passed += 1
                self.test_results.append(f"[PASS] {message}")
                return True
            else:
                self.tests_failed += 1
                self.test_results.append(f"[FAIL] {message} (expected {expected}, got {actual})")
                return False
    
    def assert_range(self, value, min_val, max_val, message):
        """Assert that value is within range."""
        if min_val <= value <= max_val:
            self.tests_passed += 1
            self.test_results.append(f"[PASS] {message}")
            return True
        else:
            self.tests_failed += 1
            self.test_results.append(f"[FAIL] {message} (value {value} not in [{min_val}, {max_val}])")
            return False
    
    # =========================================================================
    # Test 1: Basic functionality
    # =========================================================================
    
    def test_basic_topsis_execution(self):
        """Test 1: TOPSIS executes without error on valid input."""
        df = create_simple_test_data()
        weights = {
            'CPU_score': 0.25,
            'GPU_score': 0.30,
            'RAM': 0.20,
            'Storage': 0.10,
            'Final Price': 0.15
        }
        
        try:
            result = run_topsis(df, weights)
            self.assert_true(
                len(result) == 3 and 'TOPSIS_Score' in result.columns,
                "Test 1.1: TOPSIS returns correct structure"
            )
        except Exception as e:
            self.assert_true(False, f"Test 1.1: TOPSIS execution (Error: {str(e)})")
    
    # =========================================================================
    # Test 2: Score range validation
    # =========================================================================
    
    def test_score_normalization(self):
        """Test 2: TOPSIS scores are in valid range [0, 1]."""
        df = create_simple_test_data()
        weights = {'CPU_score': 0.25, 'GPU_score': 0.30, 'RAM': 0.20, 'Storage': 0.10, 'Final Price': 0.15}
        
        result = run_topsis(df, weights)
        
        scores = result['TOPSIS_Score'].values
        
        for i, score in enumerate(scores):
            self.assert_range(
                score, 0, 1,
                f"Test 2.{i+1}: TOPSIS score in [0,1] (score={score:.4f})"
            )
    
    # =========================================================================
    # Test 3: Ranking order
    # =========================================================================
    
    def test_ranking_order(self):
        """Test 3: Results are sorted by score descending."""
        df = create_simple_test_data()
        weights = {'CPU_score': 0.25, 'GPU_score': 0.30, 'RAM': 0.20, 'Storage': 0.10, 'Final Price': 0.15}
        
        result = run_topsis(df, weights)
        
        # Check rank column exists and increments
        self.assert_true(
            'Rank' in result.columns and result['Rank'].iloc[0] == 1,
            "Test 3.1: Rank column exists and starts at 1"
        )
        
        # Check scores are descending
        scores = result['TOPSIS_Score'].values
        is_descending = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
        self.assert_true(
            is_descending,
            "Test 3.2: Scores in descending order"
        )
    
    # =========================================================================
    # Test 4: Benefit vs Cost criteria
    # =========================================================================
    
    def test_benefit_vs_cost_handling(self):
        """Test 4: Benefit criteria (maximize) and Cost criteria (minimize) handled correctly."""
        df = pd.DataFrame({
            'Brand': ['A', 'B'],
            'CPU_score': [100, 50],  # Benefit: Should prefer A (higher)
            'Final Price': [10_000_000, 20_000_000]  # Cost: Should prefer A (lower)
        })
        
        weights = {'CPU_score': 0.5, 'Final Price': 0.5}
        
        result = run_topsis(df, weights)
        
        # Brand A should rank first (higher CPU, lower price)
        self.assert_equal(
            result.iloc[0]['Brand'], 'A',
            "Test 4.1: Benefit/Cost criteria applied correctly (Brand A should rank 1st)"
        )
    
    # =========================================================================
    # Test 5: Distance calculations
    # =========================================================================
    
    def test_distance_calculations(self):
        """Test 5: D+ and D- distances are calculated correctly."""
        df = create_simple_test_data()
        weights = {'CPU_score': 0.25, 'GPU_score': 0.30, 'RAM': 0.20, 'Storage': 0.10, 'Final Price': 0.15}
        
        result = run_topsis(df, weights)
        
        # Check D+ and D- columns exist
        self.assert_true(
            'D_Plus' in result.columns and 'D_Minus' in result.columns,
            "Test 5.1: D+ and D- columns exist"
        )
        
        # Check distances are non-negative
        d_plus = result['D_Plus'].values
        d_minus = result['D_Minus'].values
        
        all_non_negative = all(d_plus >= 0) and all(d_minus >= 0)
        self.assert_true(
            all_non_negative,
            "Test 5.2: All distances are non-negative"
        )
        
        # Check relationship: C* = D- / (D+ + D-)
        for idx, row in result.iterrows():
            d_plus = row['D_Plus']
            d_minus = row['D_Minus']
            topsis_score = row['TOPSIS_Score']
            
            if d_plus + d_minus > 0:
                expected_score = d_minus / (d_plus + d_minus)
                self.assert_equal(
                    topsis_score, expected_score,
                    f"Test 5.3.{idx+1}: TOPSIS score calculation correct",
                    tolerance=0.0001
                )
    
    # =========================================================================
    # Test 6: Gaming scenario (GPU priority)
    # =========================================================================
    
    def test_gaming_scenario(self):
        """Test 6: Gaming scenario prioritizes GPU."""
        df = create_gaming_test_data()
        
        # Gaming weights: GPU priority
        weights = {
            'CPU_score': 0.15,
            'GPU_score': 0.40,  # 40% to GPU
            'RAM': 0.15,
            'Storage': 0.10,
            'Final Price': 0.20
        }
        
        result = run_topsis(df, weights)
        
        # Laptops with GPU_score = 5 should generally rank higher
        top_3 = result.head(3)
        gpu_scores_top_3 = top_3['GPU_score'].values
        
        avg_gpu_top_3 = np.mean(gpu_scores_top_3)
        avg_gpu_all = np.mean(df['GPU_score'].values)
        
        self.assert_true(
            avg_gpu_top_3 >= avg_gpu_all,
            f"Test 6.1: Gaming scenario prioritizes GPU (top3 avg GPU={avg_gpu_top_3:.2f} vs all avg={avg_gpu_all:.2f})"
        )
    
    # =========================================================================
    # Test 7: Workstation scenario (RAM and CPU priority)
    # =========================================================================
    
    def test_workstation_scenario(self):
        """Test 7: Workstation scenario prioritizes RAM and CPU."""
        df = create_workstation_test_data()
        
        # Workstation weights: RAM and CPU priority
        weights = {
            'CPU_score': 0.30,
            'GPU_score': 0.05,
            'RAM': 0.40,  # 40% to RAM
            'Storage': 0.10,
            'Final Price': 0.15
        }
        
        result = run_topsis(df, weights)
        
        # Laptops with higher RAM should generally rank higher
        top_2 = result.head(2)
        ram_top_2 = top_2['RAM'].values
        
        avg_ram_top_2 = np.mean(ram_top_2)
        avg_ram_all = np.mean(df['RAM'].values)
        
        self.assert_true(
            avg_ram_top_2 >= avg_ram_all,
            f"Test 7.1: Workstation scenario prioritizes RAM (top2 avg RAM={avg_ram_top_2:.1f}GB vs all avg={avg_ram_all:.1f}GB)"
        )
    
    # =========================================================================
    # Test 8: Empty dataframe handling
    # =========================================================================
    
    def test_empty_dataframe(self):
        """Test 8: Handle empty dataframe gracefully."""
        df_empty = pd.DataFrame()
        weights = {'CPU_score': 0.5, 'Final Price': 0.5}
        
        try:
            result = run_topsis(df_empty, weights)
            self.assert_true(
                len(result) == 0,
                "Test 8.1: Empty dataframe handled gracefully"
            )
        except Exception as e:
            self.assert_true(False, f"Test 8.1: Empty dataframe (Error: {str(e)})")
    
    # =========================================================================
    # Test 9: Define criteria function
    # =========================================================================
    
    def test_define_criteria(self):
        """Test 9: Define default criteria from dataframe columns."""
        df = create_simple_test_data()
        
        criteria = define_default_criteria(df)
        
        self.assert_true(
            'CPU_score' in criteria,
            "Test 9.1: CPU_score identified as criterion"
        )
        
        self.assert_true(
            criteria['CPU_score']['type'] == 'benefit',
            "Test 9.2: CPU_score identified as benefit criterion"
        )
        
        self.assert_true(
            criteria['Final Price']['type'] == 'cost',
            "Test 9.3: Final Price identified as cost criterion"
        )
    
    # =========================================================================
    # Test 10: Summary statistics
    # =========================================================================
    
    def test_summary_statistics(self):
        """Test 10: Get TOPSIS summary with statistics."""
        df = create_simple_test_data()
        weights = {'CPU_score': 0.25, 'GPU_score': 0.30, 'RAM': 0.20, 'Storage': 0.10, 'Final Price': 0.15}
        
        result = run_topsis(df, weights)
        summary = get_topsis_summary(result, top_n=2)
        
        self.assert_equal(
            summary['total_ranked'], 3,
            "Test 10.1: Summary contains correct total count"
        )
        
        self.assert_true(
            'top_recommendations' in summary and len(summary['top_recommendations']) == 2,
            "Test 10.2: Summary contains top 2 recommendations"
        )
        
        self.assert_true(
            'score_min' in summary and 'score_max' in summary,
            "Test 10.3: Summary contains score statistics"
        )
    
    # =========================================================================
    # Test 11: Identical specs handling
    # =========================================================================
    
    def test_identical_specs(self):
        """Test 11: Handle laptops with identical specifications."""
        df = pd.DataFrame({
            'Brand': ['A', 'B'],
            'CPU_score': [100, 100],
            'GPU_score': [4, 4],
            'RAM': [16, 16],
            'Storage': [512, 512],
            'Final Price': [10_000_000, 10_000_000]
        })
        
        weights = {'CPU_score': 0.25, 'GPU_score': 0.30, 'RAM': 0.20, 'Storage': 0.10, 'Final Price': 0.15}
        
        try:
            result = run_topsis(df, weights)
            # Both should have same or very similar scores
            score_diff = abs(result.iloc[0]['TOPSIS_Score'] - result.iloc[1]['TOPSIS_Score'])
            self.assert_range(
                score_diff, 0, 0.0001,
                "Test 11.1: Identical specs produce identical scores"
            )
        except Exception as e:
            self.assert_true(False, f"Test 11.1: Identical specs (Error: {str(e)})")
    
    # =========================================================================
    # Test 12: Weight sum validation
    # =========================================================================
    
    def test_weight_sum_validation(self):
        """Test 12: TOPSIS works with weights summing to 1.0."""
        df = create_simple_test_data()
        
        weights = {'CPU_score': 0.25, 'GPU_score': 0.30, 'RAM': 0.20, 'Storage': 0.10, 'Final Price': 0.15}
        weight_sum = sum(weights.values())
        
        self.assert_equal(
            weight_sum, 1.0,
            "Test 12.1: Weights sum to 1.0",
            tolerance=0.0001
        )
        
        try:
            result = run_topsis(df, weights)
            self.assert_true(
                len(result) == len(df),
                "Test 12.2: TOPSIS executes with normalized weights"
            )
        except Exception as e:
            self.assert_true(False, f"Test 12.2: Normalized weights (Error: {str(e)})")
    
    # =========================================================================
    # Test 13: Large dataset
    # =========================================================================
    
    def test_large_dataset(self):
        """Test 13: TOPSIS handles larger datasets efficiently."""
        # Create 100 laptops
        np.random.seed(42)
        n_laptops = 100
        
        df_large = pd.DataFrame({
            'Brand': [f'Brand_{i}' for i in range(n_laptops)],
            'Model': [f'Model_{i}' for i in range(n_laptops)],
            'CPU_score': np.random.randint(40, 100, n_laptops),
            'GPU_score': np.random.randint(1, 5, n_laptops),
            'RAM': np.random.choice([8, 16, 32, 64], n_laptops),
            'Storage': np.random.choice([256, 512, 1000], n_laptops),
            'Final Price': np.random.randint(5_000_000, 100_000_000, n_laptops)
        })
        
        weights = {'CPU_score': 0.25, 'GPU_score': 0.30, 'RAM': 0.20, 'Storage': 0.10, 'Final Price': 0.15}
        
        try:
            result = run_topsis(df_large, weights)
            self.assert_true(
                len(result) == n_laptops and 'Rank' in result.columns,
                f"Test 13.1: TOPSIS handles {n_laptops} laptops correctly"
            )
        except Exception as e:
            self.assert_true(False, f"Test 13.1: Large dataset (Error: {str(e)})")
    
    # =========================================================================
    # Test 14: NaN value handling
    # =========================================================================
    
    def test_nan_handling(self):
        """Test 14: Handle NaN values in data."""
        df = pd.DataFrame({
            'Brand': ['A', 'B', 'C'],
            'CPU_score': [100, np.nan, 75],
            'GPU_score': [4, 3, np.nan],
            'RAM': [16, 32, 16],
            'Storage': [512, 512, 256],
            'Final Price': [10_000_000, 15_000_000, 8_000_000]
        })
        
        weights = {'CPU_score': 0.25, 'GPU_score': 0.30, 'RAM': 0.20, 'Storage': 0.10, 'Final Price': 0.15}
        
        try:
            result = run_topsis(df, weights)
            self.assert_true(
                len(result) == 3 and not result['TOPSIS_Score'].isna().any(),
                "Test 14.1: NaN values handled and results produced"
            )
        except Exception as e:
            self.assert_true(False, f"Test 14.1: NaN handling (Error: {str(e)})")
    
    # =========================================================================
    # Report
    # =========================================================================
    
    def run_all_tests(self):
        """Run all tests and generate report."""
        print("\n" + "="*80)
        print("PHASE 2 TEST SUITE: TOPSIS RANKING ENGINE")
        print("="*80 + "\n")
        
        # Run all test methods
        self.test_basic_topsis_execution()
        self.test_score_normalization()
        self.test_ranking_order()
        self.test_benefit_vs_cost_handling()
        self.test_distance_calculations()
        self.test_gaming_scenario()
        self.test_workstation_scenario()
        self.test_empty_dataframe()
        self.test_define_criteria()
        self.test_summary_statistics()
        self.test_identical_specs()
        self.test_weight_sum_validation()
        self.test_large_dataset()
        self.test_nan_handling()
        
        # Print report
        print("\n" + "="*80)
        print("TEST RESULTS")
        print("="*80 + "\n")
        
        for result in self.test_results:
            print(f"  {result}")
        
        total = self.tests_passed + self.tests_failed
        pass_rate = (self.tests_passed / total * 100) if total > 0 else 0
        
        print(f"\n{'='*80}")
        print(f"SUMMARY: {self.tests_passed}/{total} tests passed ({pass_rate:.1f}%)")
        print("="*80 + "\n")
        
        return self.tests_passed, self.tests_failed


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    tester = TestTOPSISEngine()
    passed, failed = tester.run_all_tests()
    
    # Exit code based on test results
    sys.exit(0 if failed == 0 else 1)
